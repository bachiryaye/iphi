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
}

/** Thin lifecycle wrapper; the option is built elsewhere so it can be tested without a DOM. */
export function EChart({ option, height }: EChartProps) {
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

  return <div ref={ref} style={{ height }} aria-hidden="true" />;
}
