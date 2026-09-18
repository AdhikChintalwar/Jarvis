export async function onRequest(context) {
  const incomingUrl = new URL(context.request.url);

  const targetUrl =
    "https://baby-investor.duckdns.org" +
    incomingUrl.pathname +
    incomingUrl.search;

  const headers = new Headers(context.request.headers);

  headers.set("X-Baby-Proxy-Secret", context.env.BABY_PROXY_SECRET);
  headers.delete("host");

  const requestInit = {
    method: context.request.method,
    headers,
    redirect: "manual",
  };

  if (!["GET", "HEAD"].includes(context.request.method)) {
    requestInit.body = context.request.body;
  }

  return fetch(targetUrl, requestInit);
}
