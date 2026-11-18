import { LineChart } from "echarts/charts";
import {
  GridComponent,
  MarkLineComponent,
  MarkPointComponent,
  TooltipComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { SVGRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";

echarts.use([
  LineChart,
  GridComponent,
  TooltipComponent,
  MarkLineComponent,
  MarkPointComponent,
  SVGRenderer,
]);

export type ChartOption = echarts.EChartsCoreOption;

interface EChartProps {
  option: ChartOption;
  height: number;
  cursor?: number | null;
  onCursor?: ((at: number | null) => void) | undefined;
}

/** Thin lifecycle wrapper; the option is built elsewhere so it can be tested without a DOM. */
export function EChart({ option, height, cursor = null, onCursor }: EChartProps) {
  const ref = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.EChartsType | null>(null);

  useEffect(() => {
    const element = ref.current;
    if (element === null) return;
    const instance = echarts.init(element, null, { renderer: "svg" });
    chart.current = instance;
    const observer =
      typeof ResizeObserver === "undefined"
        ? null
        : new ResizeObserver(() => {
            instance.resize();
          });
    observer?.observe(element);
    return () => {
      observer?.disconnect();
      instance.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    chart.current?.setOption(option, { notMerge: true });
  }, [option]);

  useEffect(() => {
    const instance = chart.current;
    if (instance === null || onCursor === undefined) return;
    const move = (event: { offsetX: number; offsetY: number }) => {
      const value: unknown = instance.convertFromPixel({ xAxisIndex: 0 }, event.offsetX);
      if (
        typeof value === "number" &&
        instance.containPixel({ gridIndex: 0 }, [event.offsetX, event.offsetY])
      )
        onCursor(value);
    };
    const leave = () => {
      onCursor(null);
    };
    instance.getZr().on("mousemove", move);
    instance.getZr().on("globalout", leave);
    return () => {
      if (!instance.isDisposed()) {
        instance.getZr().off("mousemove", move);
        instance.getZr().off("globalout", leave);
      }
    };
  }, [onCursor]);

  useEffect(() => {
    const instance = chart.current;
    if (instance === null) return;
    if (cursor === null) {
      instance.dispatchAction({ type: "hideTip" });
      return;
    }
    const x: unknown = instance.convertToPixel({ xAxisIndex: 0 }, cursor);
    if (typeof x === "number") instance.dispatchAction({ type: "showTip", x, y: height / 2 });
  }, [cursor, height, option]);

  return <div ref={ref} style={{ height }} aria-hidden="true" />;
}
