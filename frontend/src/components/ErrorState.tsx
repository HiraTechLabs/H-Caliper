import { AlertCircle, RefreshCw } from "lucide-react";

export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div className="card flex flex-col items-center px-6 py-10 text-center">
      <AlertCircle className="h-8 w-8 text-red-500" />
      <p className="mt-3 text-sm font-semibold text-ink-900">Couldn’t load this page</p>
      <p className="mt-1 max-w-xl text-xs leading-5 text-ink-500">{message}</p>
      {retry ? <button className="btn-secondary btn-sm mt-4" onClick={retry}><RefreshCw className="h-3.5 w-3.5" />Try again</button> : null}
    </div>
  );
}
