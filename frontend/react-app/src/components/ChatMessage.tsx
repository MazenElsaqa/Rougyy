import { QueryInspector } from "./QueryInspector"
import type { AskResponse } from "../lib/api"

export interface ChatEntry {
  id: string
  question: string
  response: AskResponse | null
  pending: boolean
  clientError: string | null
}

export function ChatMessage({ entry }: { entry: ChatEntry }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-lg bg-foreground px-3.5 py-2 text-sm text-background text-pretty">
          {entry.question}
        </div>
      </div>

      <div className="flex justify-start">
        <div className="max-w-[85%] w-full">
          {entry.pending && (
            <div className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3.5 py-2.5 text-sm text-muted">
              <span className="flex gap-1" aria-hidden="true">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-muted-foreground [animation-delay:0ms]" />
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-muted-foreground [animation-delay:150ms]" />
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-muted-foreground [animation-delay:300ms]" />
              </span>
              <span>Thinking</span>
            </div>
          )}

          {!entry.pending && entry.clientError && (
            <div className="rounded-lg border border-destructive/20 bg-destructive-muted px-3.5 py-2.5 text-sm text-destructive">
              {entry.clientError}
            </div>
          )}

          {!entry.pending && entry.response && (
            <div>
              {entry.response.error ? (
                <div className="rounded-lg border border-destructive/20 bg-destructive-muted px-3.5 py-2.5 text-sm text-destructive text-pretty">
                  {entry.response.error}
                </div>
              ) : (
                <div className="rounded-lg border border-border bg-surface px-3.5 py-2.5 text-sm text-foreground text-pretty leading-relaxed">
                  {entry.response.answer}
                </div>
              )}

              <QueryInspector
                sql={entry.response.sql}
                queryResult={entry.response.query_result}
                attempts={entry.response.attempts}
                linkedTables={entry.response.linked_tables}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
