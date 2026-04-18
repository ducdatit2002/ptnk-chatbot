import { NextRequest, NextResponse } from "next/server";

const backendBaseUrl = process.env.BACKEND_API_URL || "http://127.0.0.1:8000";

export async function POST(request: NextRequest) {
  const payload = await request.json();

  try {
    const response = await fetch(`${backendBaseUrl.replace(/\/$/, "")}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      cache: "no-store",
    });

    const text = await response.text();
    const contentType = response.headers.get("content-type") ?? "application/json";

    return new NextResponse(text, {
      status: response.status,
      headers: {
        "Content-Type": contentType,
      },
    });
  } catch {
    return NextResponse.json(
      {
        error: "Không thể kết nối tới backend API.",
      },
      { status: 502 },
    );
  }
}
