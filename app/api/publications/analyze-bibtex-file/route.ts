import {NextResponse} from "next/server";

// This analysis can legitimately take longer than an ordinary API request and
// returns source provenance for hundreds of rows.  Stream only this bounded
// upload endpoint instead of routing it through Next's generic rewrite proxy.
export const runtime = "nodejs";
export const maxDuration = 120;

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";
const ANALYSIS_PATH = "/publications/analyze-bibtex-file";

function backendUrl() {
  return new URL(ANALYSIS_PATH, BACKEND_URL).toString();
}

export async function POST(request: Request) {
  const controller = new AbortController();
  const abort = () => controller.abort();
  request.signal.addEventListener("abort", abort, {once: true});
  try {
    const contentType = request.headers.get("content-type");
    if (!contentType?.toLowerCase().startsWith("multipart/form-data")) {
      return NextResponse.json({detail: "BibTeX analysis requires multipart form data."}, {status: 415});
    }
    const response = await fetch(backendUrl(), {
      method: "POST",
      headers: {"content-type": contentType, accept: "application/json"},
      body: request.body,
      signal: controller.signal,
      // Node's fetch requires this for a streaming request body.  It avoids
      // buffering multi-megabyte source files in the Next.js proxy layer.
      duplex: "half",
    } as RequestInit);
    const headers = new Headers();
    for (const name of ["content-type", "content-length", "cache-control"]) {
      const value = response.headers.get(name);
      if (value) headers.set(name, value);
    }
    return new Response(response.body, {status: response.status, headers});
  } catch (cause) {
    if (controller.signal.aborted) {
      return NextResponse.json({detail: "BibTeX analysis was cancelled."}, {status: 499});
    }
    console.error("BibTeX analysis backend proxy failed", cause);
    return NextResponse.json({detail: "The analysis service connection was interrupted. Please retry the upload."}, {status: 502});
  } finally {
    request.signal.removeEventListener("abort", abort);
  }
}
