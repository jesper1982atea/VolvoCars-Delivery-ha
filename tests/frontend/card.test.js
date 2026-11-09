import assert from "node:assert/strict";
import { after, test } from "node:test";
import { Window } from "happy-dom";

const window = new Window();
for (const key of [
  "document",
  "HTMLElement",
  "customElements",
  "CustomEvent",
]) {
  globalThis[key] = window[key];
}
globalThis.window = window;
await import("../../custom_components/volvo_delivery/frontend/volvo-delivery-card.js");
after(() => window.happyDOM.abort());

function state(field, value, attrs = {}, trackingId = "order-a") {
  return {
    state: value,
    attributes: {
      delivery_tracking_id: trackingId,
      delivery_field: field,
      ...attrs,
    },
  };
}

function hass() {
  return {
    config: { time_zone: "Europe/Stockholm" },
    states: {
      "sensor.my_renamed_status": state("status", "Din bil är orderlagd.", {
        model: "EX60",
        specification: "En fiktiv bil",
      }),
      "sensor.my_delivery": state(
        "delivery_estimate",
        "Leverans beräknad till v. 5",
        {
          estimated_start: "2027-02-01",
          estimated_end: "2027-02-07",
          delivery_week: 5,
          year_source: "inferred",
        },
      ),
      "sensor.checked": state("last_checked", "2026-11-09T12:00:00+00:00"),
      "sensor.changed": state("last_changed", "2026-11-08T12:00:00+00:00"),
      "sensor.changes": state(
        "order_changes",
        "Ändringar möjliga till 2026-11-12",
        {
          description: "Kontakta din säljare",
        },
      ),
      "sensor.another_order": state(
        "delivery_estimate",
        "Other order",
        {
          estimated_start: "2027-02-01",
          estimated_end: "2027-02-07",
        },
        "order-b",
      ),
    },
    callService: async () => {},
  };
}

function card(t, now = "2026-11-09T12:00:00Z", data = hass()) {
  t.mock.timers.enable({ apis: ["Date"], now: new Date(now) });
  const element = document.createElement("volvo-delivery-card");
  element.setConfig({ status_entity: "sensor.my_renamed_status" });
  element.hass = data;
  return element;
}

function text(card, selector) {
  return card.shadowRoot.querySelector(selector).textContent;
}

test("discovers sensors from the selected order and shows an 84-day countdown", (t) => {
  const element = card(t);
  assert.equal(text(element, ".number"), "84");
  assert.equal(text(element, ".week-number"), "v. 5");
  assert.match(text(element, ".range"), /1 feb.*2027.*7 feb.*2027/);
  assert.match(text(element, ".forecast-note"), /Årtalet är uppskattat/);
  assert.equal(text(element, ".model"), "EX60");
  assert.match(text(element, ".updated"), /2026-11-09/);
  assert.equal(
    element.shadowRoot
      .querySelector(".timeline li")
      .getAttribute("aria-current"),
    "step",
  );
  assert.equal(element.shadowRoot.querySelector(".notice").hidden, true);
});

test("counts calendar days in HA timezone, not browser timezone", (t) => {
  const element = card(t, "2027-01-31T23:30:00Z");
  assert.equal(text(element, ".number"), "0");
  assert.match(text(element, ".countdown-label"), /pågår/);
});

test("counts across daylight saving without fractional days", (t) => {
  const data = hass();
  Object.assign(data.states["sensor.my_delivery"].attributes, {
    estimated_start: "2027-03-29",
    estimated_end: "2027-04-04",
    delivery_week: 13,
  });
  const element = card(t, "2027-03-27T23:30:00Z", data);
  assert.equal(text(element, ".number"), "1");
  assert.equal(text(element, ".unit"), "dag");
});

test("past forecast never rolls to next year or claims delivery", (t) => {
  const element = card(t, "2027-02-08T10:00:00Z");
  assert.equal(text(element, ".number"), "–");
  assert.match(text(element, ".countdown-label"), /passerat/);
  assert.match(text(element, ".range"), /2027/);
  assert.doesNotMatch(text(element, "h1"), /Välkommen hem/);
});

test("delivered status stops countdown", (t) => {
  const data = hass();
  data.states["sensor.my_renamed_status"].state =
    "Grattis! Din nya bil är levererad.";
  const element = card(t, undefined, data);
  assert.equal(text(element, ".number"), "–");
  assert.equal(text(element, "h1"), "Välkommen hem.");
});

test("missing date support shows Volvo text without guessed dates", (t) => {
  const data = hass();
  delete data.states["sensor.my_delivery"].attributes.estimated_start;
  const element = card(t, undefined, data);
  assert.equal(text(element, ".number"), "–");
  assert.equal(text(element, ".range"), "Leverans beräknad till v. 5");
  assert.match(text(element, ".forecast-note"), /räcker inte/);
});

test("unavailable status and estimate do not show stale countdown", (t) => {
  const data = hass();
  data.states["sensor.my_renamed_status"].state = "unavailable";
  data.states["sensor.my_delivery"].state = "unavailable";
  const element = card(t, undefined, data);
  assert.equal(text(element, ".number"), "–");
  assert.equal(element.shadowRoot.querySelector(".notice").hidden, false);
  assert.match(text(element, ".notice"), /behörighet/);
});

test("missing status shows a configuration error", (t) => {
  const data = hass();
  delete data.states["sensor.my_renamed_status"];
  const element = card(t, undefined, data);
  assert.match(text(element, ".notice"), /hittades inte/);
  assert.equal(element.shadowRoot.querySelector(".refresh").disabled, true);
});

test("rejects malformed configuration", () => {
  const element = document.createElement("volvo-delivery-card");
  for (const config of [
    {},
    { status_entity: "light.test" },
    { status_entity: 4 },
  ]) {
    assert.throws(() => element.setConfig(config), /sensor/);
  }
});

test("remote text is rendered as text, never HTML", (t) => {
  const data = hass();
  data.states["sensor.my_renamed_status"].attributes.specification =
    '<img src=x onerror="alert(1)">';
  const element = card(t, undefined, data);
  assert.match(text(element, ".subtitle"), /<img/);
  assert.equal(element.shadowRoot.querySelector(".subtitle img"), null);
  assert.equal(
    element.shadowRoot.querySelector(".vehicle-specification img"),
    null,
  );
});

test("refresh calls HA once and shows service errors to the user", async (t) => {
  const data = hass();
  let calls = 0;
  data.callService = async (domain, service, args) => {
    calls++;
    assert.equal(domain, "homeassistant");
    assert.equal(service, "update_entity");
    assert.equal(args.entity_id, "sensor.my_renamed_status");
    throw new Error("Permission denied");
  };
  const element = card(t, undefined, data);
  await element._refresh();
  assert.equal(calls, 1);
  assert.equal(element.shadowRoot.querySelector(".action-error").hidden, false);
  assert.equal(element.shadowRoot.querySelector(".refresh").disabled, false);
});

test("more-info opens the configured status sensor", (t) => {
  const element = card(t);
  let detail;
  element.addEventListener("hass-more-info", (event) => {
    detail = event.detail;
  });
  element.shadowRoot.querySelector(".status-button").click();
  assert.deepEqual(detail, { entityId: "sensor.my_renamed_status" });
});

test("editor registers with HA and emits config changes safely", () => {
  const Card = customElements.get("volvo-delivery-card");
  assert.equal(
    window.customCards.filter((item) => item.type === "volvo-delivery-card")
      .length,
    1,
  );
  assert.equal(
    Card.getStubConfig(hass()).status_entity,
    "sensor.my_renamed_status",
  );
  const editor = Card.getConfigElement();
  editor.setConfig({
    type: "custom:volvo-delivery-card",
    status_entity: "sensor.old",
    delivery_entity: "sensor.old_estimate",
  });
  editor.hass = hass();
  let config;
  editor.addEventListener("config-changed", (event) => {
    config = event.detail.config;
  });
  const select = editor.shadowRoot.querySelector("select");
  select.value = "sensor.my_renamed_status";
  select.dispatchEvent(new window.Event("change"));
  assert.equal(config.status_entity, "sensor.my_renamed_status");
  assert.equal(config.delivery_entity, undefined);
  assert.equal(config.type, "custom:volvo-delivery-card");
});

test("connected card updates countdown and removes its timer when detached", (t) => {
  const element = card(t);
  element.connectedCallback();
  assert.ok(element._timer);
  element.disconnectedCallback();
  assert.equal(element._timer, null);
});

test("editor preserves unsaved input when unrelated HA states change", () => {
  const editor = document.createElement("volvo-delivery-card-editor");
  editor.setConfig({ status_entity: "sensor.my_renamed_status" });
  editor.hass = hass();
  const input = editor.shadowRoot.querySelector("input");
  input.value = "Min nya rubrik";
  const data = hass();
  data.states["sensor.unrelated"] = { state: "on", attributes: {} };
  editor.hass = data;
  assert.equal(editor.shadowRoot.querySelector("input"), input);
  assert.equal(input.value, "Min nya rubrik");
});

function withVehicleMedia() {
  const data = hass();
  Object.assign(data.states["sensor.my_renamed_status"].attributes, {
    image_url: "https://wizz.volvocars.com/images/example.png?w=600",
    image_alt: "Volvo example",
    rear_image_url: "https://wizz.volvocars.com/images/rear.png",
    interior_image_url: "https://wizz.volvocars.com/images/interior.png",
    model_url: "https://www.volvocars.com/se/cars/ex60-electric",
    manual_url: "https://www.volvocars.com/se/support/car/ex60",
  });
  return data;
}

test("uses Volvo image URLs and configuration without exposing credentials", (t) => {
  const data = withVehicleMedia();
  const element = card(t, undefined, data);
  const image = element.shadowRoot.querySelector(".main-image");
  assert.equal(
    image.getAttribute("src"),
    data.states["sensor.my_renamed_status"].attributes.image_url,
  );
  assert.equal(image.alt, "Volvo example");
  assert.equal(image.getAttribute("referrerpolicy"), "no-referrer");
  assert.equal(
    element.shadowRoot.querySelector(".vehicle-photo").hidden,
    false,
  );
  assert.equal(
    element.shadowRoot.querySelector(".scene").hasAttribute("hidden"),
    true,
  );
  assert.equal(element.shadowRoot.querySelector(".image-notice").hidden, true);
  assert.equal(element.shadowRoot.querySelector(".rear-photo").hidden, false);
  assert.equal(
    element.shadowRoot.querySelector(".interior-photo").hidden,
    false,
  );
  assert.equal(
    element.shadowRoot.querySelector(".vehicle-details").hidden,
    false,
  );
  assert.equal(text(element, ".vehicle-specification"), "En fiktiv bil");
  const link = element.shadowRoot.querySelector(".model-link");
  assert.equal(
    link.getAttribute("href"),
    data.states["sensor.my_renamed_status"].attributes.model_url,
  );
  assert.equal(link.getAttribute("rel"), "noopener noreferrer");
  assert.match(
    text(element, ".vehicle-note"),
    /inte en fullständig utrustningslista/,
  );
});

test("failed Volvo main image shows explicit notice and generic illustration", (t) => {
  const element = card(t, undefined, withVehicleMedia());
  element.shadowRoot
    .querySelector(".main-image")
    .dispatchEvent(new window.Event("error"));
  assert.equal(element.shadowRoot.querySelector(".vehicle-photo").hidden, true);
  assert.equal(
    element.shadowRoot.querySelector(".scene").hasAttribute("hidden"),
    false,
  );
  assert.equal(element.shadowRoot.querySelector(".image-notice").hidden, false);
  assert.match(text(element, ".image-notice"), /kunde inte visas/);
  element.hass = withVehicleMedia();
  assert.equal(
    element.shadowRoot.querySelector(".main-image").getAttribute("src"),
    null,
  );
});

test("failed gallery image is reported without hiding other images", (t) => {
  const element = card(t, undefined, withVehicleMedia());
  element.shadowRoot
    .querySelector(".rear-image")
    .dispatchEvent(new window.Event("error"));
  assert.equal(element.shadowRoot.querySelector(".rear-photo").hidden, true);
  assert.equal(
    element.shadowRoot.querySelector(".interior-photo").hidden,
    false,
  );
  assert.equal(
    element.shadowRoot.querySelector(".gallery-notice").hidden,
    false,
  );
});

test("no supplied images keeps a clearly labelled generic illustration", (t) => {
  const element = card(t);
  assert.equal(element.shadowRoot.querySelector(".vehicle-photo").hidden, true);
  assert.equal(
    element.shadowRoot.querySelector(".scene").hasAttribute("hidden"),
    false,
  );
  assert.match(text(element, ".image-notice"), /Illustrationen är generell/);
});

test("changed or removed image URL does not keep a previous order image", (t) => {
  const element = card(t, undefined, withVehicleMedia());
  const data = withVehicleMedia();
  data.states["sensor.my_renamed_status"].attributes.image_url =
    "https://wizz.volvocars.com/images/updated.png";
  element.hass = data;
  assert.equal(
    element.shadowRoot.querySelector(".main-image").getAttribute("src"),
    "https://wizz.volvocars.com/images/updated.png",
  );
  element.hass = hass();
  assert.equal(
    element.shadowRoot.querySelector(".main-image").getAttribute("src"),
    null,
  );
});

test("unsafe images and links are never assigned to DOM attributes", (t) => {
  const data = withVehicleMedia();
  Object.assign(data.states["sensor.my_renamed_status"].attributes, {
    image_url: "https://example.invalid/image.png",
    rear_image_url: "javascript:alert(1)",
    interior_image_url: "https://user:password@wizz.volvocars.com/image.png",
    model_url: "javascript:alert(1)",
    manual_url: "https://www.volvocars.com.example.invalid/",
  });
  const element = card(t, undefined, data);
  for (const selector of [".main-image", ".rear-image", ".interior-image"]) {
    assert.equal(
      element.shadowRoot.querySelector(selector).getAttribute("src"),
      null,
    );
  }
  for (const selector of [".model-link", ".manual-link"]) {
    assert.equal(
      element.shadowRoot.querySelector(selector).getAttribute("href"),
      null,
    );
  }
  assert.equal(element.shadowRoot.querySelector(".image-notice").hidden, false);
});

test("unavailable status does not show stale media or model links", (t) => {
  const data = withVehicleMedia();
  data.states["sensor.my_renamed_status"].state = "unavailable";
  const element = card(t, undefined, data);
  assert.equal(
    element.shadowRoot.querySelector(".main-image").getAttribute("src"),
    null,
  );
  assert.equal(
    element.shadowRoot.querySelector(".model-link").getAttribute("href"),
    null,
  );
  assert.equal(
    element.shadowRoot.querySelector(".vehicle-details").hidden,
    true,
  );
});
