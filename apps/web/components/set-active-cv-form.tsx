"use client";
import { useActionState } from "react";
import { setActiveCv } from "@/app/cvs/actions";

type SetActiveCvFormProps = {
  cvId: string;
  isActive: boolean;
};

export function SetActiveCvForm({ cvId, isActive }: SetActiveCvFormProps) {
  const [state, formAction, pending] = useActionState(setActiveCv, { error: null });
  return (
    <form action={formAction} className="flex flex-col items-end gap-1">
      <input type="hidden" name="cvId" value={cvId} />
      <button
        type="submit"
        disabled={isActive || pending}
        className="rounded border border-gray-300 px-3 py-1 text-sm hover:bg-gray-50 disabled:cursor-default disabled:opacity-50"
      >
        {pending ? "Activating…" : isActive ? "Active" : "Set active"}
      </button>
      {state.error && <p className="text-xs text-red-600">{state.error}</p>}
    </form>
  );
}