import { createServer } from "node:http";
import { readFile } from "node:fs/promises";

const routes = new Map([
  [
    "/",
    [new URL("./preview.html", import.meta.url), "text/html; charset=utf-8"],
  ],
  [
    "/volvo-delivery-card.js",
    [
      new URL(
        "../../custom_components/volvo_delivery/frontend/volvo-delivery-card.js",
        import.meta.url,
      ),
      "application/javascript; charset=utf-8",
    ],
  ],
]);
const port = Number(process.env.PORT || 8765);
createServer(async (request, response) => {
  const route = routes.get(new URL(request.url, "http://localhost").pathname);
  if (!route) {
    response.writeHead(404);
    response.end("Not found");
    return;
  }
  try {
    const body = await readFile(route[0]);
    response.writeHead(200, {
      "Content-Type": route[1],
      "Cache-Control": "no-store",
    });
    response.end(body);
  } catch (error) {
    console.error("Could not read preview asset:", error);
    response.writeHead(500);
    response.end("Could not load preview");
  }
}).listen(port, "127.0.0.1", () => {
  console.log(`Volvo Delivery demo ready at http://127.0.0.1:${port}`);
});
