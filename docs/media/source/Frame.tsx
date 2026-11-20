import React from "react";
import { AbsoluteFill, Still, registerRoot } from "remotion";

import chapters from "./chapters.json";

const palette = {
  background: "#F3F4F6",
  surface: "#FFFFFF",
  text: "#1A1F26",
  muted: "#556070",
  border: "#D9DCE1",
};

const Frame = ({ index }: { index: number }) => {
  const chapter = chapters[index];
  if (!chapter) throw new Error("Unknown demonstration chapter");

  return (
    <AbsoluteFill
      lang="fr"
      style={{
        background: palette.background,
        color: palette.text,
        fontFamily: "'IBM Plex Sans', 'DejaVu Sans', sans-serif",
      }}
    >
      <header
        style={{
          position: "absolute",
          inset: "24px 24px auto",
          display: "flex",
          alignItems: "baseline",
          gap: 28,
          borderBottom: `1px solid ${palette.border}`,
          paddingBottom: 20,
        }}
      >
        <h1 style={{ margin: 0, fontSize: 56, fontWeight: 600 }}>IPHI</h1>
        <p style={{ margin: 0, fontSize: 30 }}>
          Santé d’une plateforme de données industrielles
        </p>
        <p style={{ margin: "0 0 0 auto", fontSize: 25, color: palette.muted }}>
          Données simulées
        </p>
      </header>
      <main>
        <div
          aria-label="Zone réservée à la capture réelle du navigateur"
          style={{
            position: "absolute",
            left: 23,
            top: 143,
            width: 1442,
            height: 902,
            background: palette.surface,
            border: `1px solid ${palette.border}`,
            boxSizing: "border-box",
          }}
        />
        <aside
          style={{ position: "absolute", left: 1500, top: 144, width: 388 }}
        >
          <p style={{ margin: "0 0 24px", fontSize: 25, color: palette.muted }}>
            Étape {index + 1} / {chapters.length}
          </p>
          <h2
            style={{
              margin: "0 0 32px",
              fontSize: 42,
              fontWeight: 600,
              lineHeight: 1.15,
            }}
          >
            {chapter.title}
          </h2>
          <p style={{ margin: 0, fontSize: 30, lineHeight: 1.45 }}>
            {chapter.text}
          </p>
        </aside>
        <p
          style={{
            position: "absolute",
            left: 1500,
            bottom: 92,
            width: 388,
            margin: 0,
            fontSize: 25,
            lineHeight: 1.4,
            color: palette.muted,
          }}
        >
          {chapter.note}
        </p>
      </main>
      <footer
        style={{
          position: "absolute",
          right: 32,
          bottom: 28,
          fontSize: 23,
          color: palette.muted,
        }}
      >
        github.com/bachiryaye/iphi
      </footer>
    </AbsoluteFill>
  );
};

registerRoot(() => (
  <Still
    id="Chapter"
    component={Frame}
    width={1920}
    height={1080}
    defaultProps={{ index: 0 }}
  />
));
