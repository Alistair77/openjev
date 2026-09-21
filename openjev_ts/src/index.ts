export type ChoiceQuestion = { type: "choice"; instructions: unknown; criteria: Record<string, unknown> };
export type ScoreQuestion = { type: "score"; instructions: unknown; criteria: unknown[] };
export type NoulQuestion = { type: "noul"; instructions: unknown };
export type Question = ChoiceQuestion | ScoreQuestion | NoulQuestion;
export type EvaluateRequest = { api_version?: "v1"; state: unknown; questions: Record<string, Question>; options?: { abstain_below?: number; top_k?: number; seed?: number; trace?: boolean; timeout_seconds?: number } };
export type EvaluateResponse = { api_version: "v1"; request_id: string; model: string; backend: string; answers: Record<string, unknown>; latency_ms: number; trace: unknown[] };

export class OpenJevClient {
  constructor(private readonly baseUrl = "http://127.0.0.1:8787", private readonly token?: string) {}
  async evaluate(request: EvaluateRequest): Promise<EvaluateResponse> {
    const response = await fetch(`${this.baseUrl}/v1/evaluate`, { method: "POST", headers: { "content-type": "application/json", ...(this.token ? { authorization: `Bearer ${this.token}` } : {}) }, body: JSON.stringify(request) });
    if (!response.ok) throw new Error(`OpenJev request failed: ${response.status}`);
    return response.json() as Promise<EvaluateResponse>;
  }
}
