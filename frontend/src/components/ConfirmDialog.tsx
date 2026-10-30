import { Modal } from "@/components/Modal";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  danger?: boolean;
  busy?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export function ConfirmDialog({ open, title, description, confirmLabel = "Confirm", danger = false, busy = false, onCancel, onConfirm }: ConfirmDialogProps) {
  return <Modal open={open} title={title} onClose={onCancel} footer={<><button className="btn-secondary" onClick={onCancel} disabled={busy}>Cancel</button><button className={danger ? "btn-danger" : "btn-primary"} onClick={onConfirm} disabled={busy}>{busy ? "Working…" : confirmLabel}</button></>}><p className="text-sm leading-6 text-ink-600">{description}</p></Modal>;
}
