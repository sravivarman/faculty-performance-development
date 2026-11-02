"use client";

import { useEffect, useRef, useState } from "react";

type DeleteConfirmationDialogProps = {
  open: boolean;
  title: string;
  recordName: string;
  description?: string;
  dependencyWarning?: string;
  busy?: boolean;
  error?: string;
  requireTypedConfirmation?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

/** A small, shared confirmation dialog for genuinely permanent deletions. */
export default function DeleteConfirmationDialog({
  open,
  title,
  recordName,
  description = "This action permanently removes this record. It cannot be undone.",
  dependencyWarning,
  busy = false,
  error,
  requireTypedConfirmation = false,
  onCancel,
  onConfirm,
}: DeleteConfirmationDialogProps) {
  const cancelButton = useRef<HTMLButtonElement>(null);
  const [confirmation, setConfirmation] = useState("");
  useEffect(() => {
    if (!open) return;
    setConfirmation("");
    cancelButton.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) onCancel();
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [busy, onCancel, open]);

  if (!open) return null;

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget && !busy) onCancel();
    }}>
      <section className="dialog danger-panel" role="dialog" aria-modal="true" aria-labelledby="delete-dialog-title" aria-describedby="delete-dialog-description">
        <h2 id="delete-dialog-title">{title}</h2>
        <p><strong>{recordName}</strong></p>
        <p id="delete-dialog-description" className="muted">{description}</p>
        {dependencyWarning && <p className="notice">{dependencyWarning}</p>}
        {error && <div className="error" role="alert">{error}</div>}
        {requireTypedConfirmation && <label className="field">Type DELETE to confirm<input aria-label="Type DELETE to confirm" value={confirmation} autoComplete="off" onChange={(event) => setConfirmation(event.target.value)}/></label>}
        <div className="actions">
          <button ref={cancelButton} type="button" className="secondary" disabled={busy} onClick={onCancel}>Cancel</button>
          <button type="button" className="danger" disabled={busy || (requireTypedConfirmation && confirmation !== "DELETE")} onClick={onConfirm}>{busy ? "Deleting…" : "Delete"}</button>
        </div>
      </section>
    </div>
  );
}
