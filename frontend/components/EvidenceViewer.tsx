"use client";

import Editor from "@monaco-editor/react";
import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { Evidence } from "@/lib/types";

function useIsDark() {
  const [dark, setDark] = useState(true);
  useEffect(() => {
    const el = document.documentElement;
    const update = () => setDark(el.classList.contains("dark"));
    update();
    const obs = new MutationObserver(update);
    obs.observe(el, { attributes: true, attributeFilter: ["class"] });
    return () => obs.disconnect();
  }, []);
  return dark;
}

export function EvidenceViewer({
  submissionId,
  evidence,
}: {
  submissionId: string;
  evidence: Evidence | null;
}) {
  const [content, setContent] = useState("");
  const [language, setLanguage] = useState<string | undefined>(undefined);
  const dark = useIsDark();
  const editorRef = useRef<any>(null);
  const monacoRef = useRef<any>(null);
  const decorationsRef = useRef<string[]>([]);

  useEffect(() => {
    if (!evidence) return;
    let cancelled = false;
    api
      .fileContent(submissionId, evidence.path)
      .then((r) => {
        if (cancelled) return;
        setContent(r.content);
        setLanguage(r.language || undefined);
      })
      .catch(() => setContent("// Could not load file content"));
    return () => {
      cancelled = true;
    };
  }, [submissionId, evidence?.path]);

  function applyHighlight() {
    const editor = editorRef.current;
    const monaco = monacoRef.current;
    if (!editor || !monaco || !evidence) return;
    const start = Math.max(1, evidence.start_line);
    const end = Math.max(start, evidence.end_line);
    decorationsRef.current = editor.deltaDecorations(decorationsRef.current, [
      {
        range: new monaco.Range(start, 1, end, 1),
        options: {
          isWholeLine: true,
          className: "evidence-line",
          linesDecorationsClassName: "evidence-gutter",
        },
      },
    ]);
    editor.revealLineInCenter(start);
  }

  useEffect(() => {
    applyHighlight();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [content, evidence?.start_line, evidence?.end_line]);

  if (!evidence) {
    return (
      <div className="card-2 grid h-[440px] place-items-center p-6 text-center text-sm text-muted">
        Select a verified evidence item to view the cited code.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border">
      <div className="flex items-center justify-between border-b bg-surface2 px-3.5 py-2.5 font-mono text-xs text-muted">
        <span className="truncate">{evidence.path}</span>
        <span>
          L{evidence.start_line}–{evidence.end_line}
        </span>
      </div>
      <Editor
        height="440px"
        theme={dark ? "vs-dark" : "light"}
        language={language}
        value={content}
        onMount={(editor, monaco) => {
          editorRef.current = editor;
          monacoRef.current = monaco;
          applyHighlight();
        }}
        options={{
          readOnly: true,
          minimap: { enabled: false },
          fontSize: 12,
          lineNumbers: "on",
          scrollBeyondLastLine: false,
          renderLineHighlight: "none",
          padding: { top: 10 },
        }}
      />
      <style jsx global>{`
        .evidence-line {
          background: rgb(var(--primary) / 0.16);
        }
        .evidence-gutter {
          background: rgb(var(--primary));
          width: 3px !important;
          margin-left: 3px;
        }
      `}</style>
    </div>
  );
}
