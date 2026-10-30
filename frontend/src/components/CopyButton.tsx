import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { copyText } from "@/lib/format";

export function CopyButton({ value, label = "Copy" }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => { try { await copyText(value); setCopied(true); window.setTimeout(() => setCopied(false), 1600); } catch { setCopied(false); } };
  return <button className="btn-ghost btn-sm" onClick={() => void copy()} title={label}><>{copied ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}{copied ? "Copied" : label}</></button>;
}
