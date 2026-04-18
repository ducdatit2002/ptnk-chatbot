import { NextResponse } from "next/server";

const backendBaseUrl = process.env.BACKEND_API_URL || "http://127.0.0.1:8000";

export async function GET() {
  try {
    const response = await fetch(`${backendBaseUrl.replace(/\/$/, "")}/health`, {
      cache: "no-store",
    });
    const payload = await response.json();

    return NextResponse.json(
      {
        status: "ok",
        backendReachable: response.ok,
        backend: payload,
      },
      { status: response.ok ? 200 : response.status },
    );
  } catch {
    return NextResponse.json(
      {
        status: "backend_unreachable",
        backendReachable: false,
      },
      { status: 502 },
    );
  }
}
