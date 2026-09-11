import { useEffect, useState } from "react"
import { QueryInspector } from "./QueryInspector"
import type { AskResponse, PerDatabaseAskResult } from "../lib/api"

export interface ChatEntry {
  id: string
  question: string
  response: AskResponse | null
  pending: boolean
  clientError: string | null
}

function SingleAnswer({ response }: { response: AskResponse }) {
  return (
    <div>
      {response.error ? (
        <div className="rounded-2xl rounded-tl-md border border-destructive/20 bg-destructive-muted px-4 py-3 text-sm text-destructive text-pretty">
          {response.error}
        </div>
      ) : (
        <div className="glass rounded-2xl rounded-tl-md px-4 py-3 text-sm text-foreground text-pretty leading-relaxed">
          {response.answer}
        </div>
      )}

      <QueryInspector
        sql={response.sql}
        queryResult={response.query_result}
        attempts={response.attempts}
        linkedTables={response.linked_tables}
      />
    </div>
  )
}

function MultiDatabaseAnswer({ results }: { results: PerDatabaseAskResult[] }) {
  return (
    <div className="flex flex-col gap-2.5">
      {results.map((result) => (
        <div key={result.database_id} className="glass overflow-hidden rounded-2xl rounded-tl-md">
          <div className="flex items-center gap-2 border-b border-border bg-surface-muted/60 px-4 py-2">
            <span className="h-1.5 w-1.5 rounded-full bg-primary" aria-hidden="true" />
            <span className="truncate text-[12px] font-semibold text-foreground">{result.database_name}</span>
            {result.error && <span className="text-[11px] text-destructive">failed</span>}
          </div>
          <div className="px-4 py-3 text-sm leading-relaxed text-foreground text-pretty">
            {result.error ? <span className="text-destructive">{result.error}</span> : result.answer}
          </div>
          <div className="px-4 pb-3">
            <QueryInspector
              sql={result.sql}
              queryResult={result.query_result}
              attempts={result.attempts}
              linkedTables={result.linked_tables}
            />
          </div>
        </div>
      ))}
    </div>
  )
}

export function ChatMessage({ entry }: { entry: ChatEntry }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-foreground px-4 py-2.5 text-sm text-background text-pretty">
          {entry.question}
        </div>
      </div>

      <div className="flex justify-start">
        <div className="w-full">
          {entry.pending && <ThinkingIndicator />}

          {!entry.pending && entry.clientError && (
            <div className="rounded-2xl rounded-tl-md border border-destructive/20 bg-destructive-muted px-4 py-3 text-sm text-destructive">
              {entry.clientError}
            </div>
          )}

          {!entry.pending && entry.response && (
            <>
              {entry.response.per_database && entry.response.per_database.length > 1 ? (
                <MultiDatabaseAnswer results={entry.response.per_database} />
              ) : (
                <SingleAnswer response={entry.response} />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function ThinkingIndicator() {
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    const timer = setInterval(() => setElapsed((s) => s + 1), 1000)
    return () => clearInterval(timer)
  }, [])
  return (
    <div className="glass flex items-center gap-2 rounded-2xl rounded-tl-md px-4 py-3 text-sm text-muted">
      <span className="flex gap-1" aria-hidden="true">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-muted-foreground [animation-delay:0ms]" />
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-muted-foreground [animation-delay:150ms]" />
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-muted-foreground [animation-delay:300ms]" />
      </span>
      <span>
        Thinking… {elapsed}s
        {elapsed > 20 && <span className="text-muted-foreground"> (local model, can take ~1 min)</span>}
      </span>
    </div>
  )
}
