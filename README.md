# Volvo Delivery för Home Assistant

En **inofficiell** integration för att följa en svensk Volvoorder via samma
API som [Volvos leveranssida](https://www.volvocars.com/se/delivery-information/).
Ingen koppling till den officiella integrationen för redan levererade bilar.

## Installation

Kopiera `custom_components/volvo_delivery` till
`config/custom_components/volvo_delivery` i Home Assistant och starta om.
Alternativt: lägg till det här repot som ett anpassat integrationsrepo i HACS
och installera **Volvo Delivery**. Kräver Home Assistant 2025.3 eller senare.

I HACS: öppna menyn för **Anpassade arkiv / Custom repositories**, ange
`https://github.com/jesper1982atea/VolvoCars-Delivery-ha` och välj typen
**Integration**. Hämta Volvo Delivery och starta om Home Assistant.
Kortet ingår i samma installation; inget separat frontend-repo behövs.
Välj den senaste publicerade versionen. Kortet uppdateras tillsammans med
integrationen; efter en uppdatering kan webbläsaren eller mobilappen behöva
laddas om för att läsa det nya kortet.

Öppna **Inställningar → Enheter och tjänster → Lägg till integration → Volvo
Delivery**. Ange ditt ordernummer (sju eller åtta siffror) och Authorization-värdet
enligt nedan. Flera order kan läggas till separat.

## Dashboardkort och mobilapp

Integrationen innehåller **Volvo Delivery-kortet**, med en mobilanpassad layout,
nedräkning, leveransintervall, statussteg, orderinformation och uppdateringsknapp.
Det fungerar i webbläsaren och i **Home Assistant Companion-appen** på iOS/Android.
Det är ett dashboardkort i Home Assistant, inte en separat mobilapp eller ett
Home Assistant-tillägg.

Kortets JavaScript registreras automatiskt när integrationen laddas. Efter
installationen: ladda om webbläsaren eller stäng och öppna Home Assistant-appen.
Öppna din dashboard, välj **Redigera → Lägg till kort → Volvo Delivery** och
välj orderns statussensor i den visuella redigeraren. Övriga sensorer hittas
automatiskt via orderns interna ID, även om entiteterna byter namn.
Se till att orderns leveranssensor är aktiverad.

### Bilbilder och konfiguration

Kortet visar bilbilden från Volvos leveranssvar, när en bildlänk finns.
Under **Din bil · konfiguration och bilder** visas:

- Volvos kompletta konfigurationstext, exempelvis modell, utrustningsnivå,
  drivlina och färg i den mån dessa ingår i texten.
- Ytterligare exteriör- och interiörbilder när Volvo skickar sådana länkar.
- Länkar till Volvos modellsida och manual/support.

Svaret från leverans-API:et innehåller inte ett VIN, en fullständig
utrustningslista eller strukturerade uppgifter om batterikapacitet, räckvidd
eller effekt. Integrationen försöker inte härleda detta från bildfilernas namn.
En bild kan vara en generell modellillustration och behöver inte exakt
motsvara orderns färg eller tillval.

Bilderna hämtas direkt av din webbläsare från Volvos bildservrar. De kopieras
inte in i GitHub-repot, och Authorization-värdet eller ordernumret skickas inte
med bildförfrågningarna av integrationen. Bildservrarna ser vanliga
webbförfrågningar, inklusive din IP-adress. Bildernas rättigheter tillhör
respektive rättighetsinnehavare. Om en bild saknas eller inte kan laddas visas
ett tydligt meddelande; huvudbilden ersätts då av en generell illustration.

Alternativt kan ett manuellt kort läggas till:

```yaml
type: custom:volvo-delivery-card
status_entity: sensor.volvo_1234567_leveransstatus
title: Min nya Volvo
```

Byt `status_entity` till ditt verkliga entitets-ID. Fälten `delivery_entity`,
`changes_entity`, `last_checked_entity` och `last_changed_entity` kan anges
manuellt om du inte vill använda automatisk sensoridentifiering.
Ordernummer och behörighetsvärden anges **aldrig** i kortets konfiguration.

### Nedräkning och datumprognos

Kortet visar dagar tills **måndagen i leveransveckan**, och datumintervallet
måndag–söndag. Det är en prognos, inte en bokad överlämningsdag. Under den
beräknade veckan visas att den pågår; efter veckan visas att prognosen har
passerat, inte att bilen automatiskt har levererats.

När Volvo anger vecka utan årtal används texten med antal veckor kvar som
underlag för ett uppskattat år. Kortet märker detta uttryckligen.
Exempel: vecka 5 och 12 veckor kvar, hämtat den 9 november 2026, ger
**1–7 februari 2027**, med **84 dagar** till veckans start.
Det beräknade året förankras när Volvos leveransuppskattning ändras och sparas
över omstarter, så en passerad prognos inte flyttas fram ett år av sig själv.
Om årtal eller veckoprognos saknas, eller uppgifterna är tvetydiga, visas
Volvos originaltext utan en påhittad nedräkning.

Kortet räknar kalenderdagar i Home Assistants tidszon och uppdaterar nedräkningen
ungefär varje minut medan det är aktivt. Detta gör inga extra anrop till Volvo.
Sensorn för antal dagar uppdateras vid integrationens dagliga hämtning.

## Hämta Authorization-värdet

Volvos sida använder en Bearer-header mot ett odokumenterat API. Integrationen
använder inte Volvo ID eller Connected Vehicle API. Värdet hämtas manuellt:

1. Öppna Volvos leveranssida i en vanlig webbläsare och öppna utvecklarverktygen
   (F12 eller Cmd+Option+I).
2. Välj **Network/Nätverk**, skriv ditt ordernummer och tryck **Se leveransstatus**.
3. Välj anropet till `order-delivery-backend.vcscloud.se/markets/se/orders/…`.
4. Kopiera värdet för **Authorization** under **Request Headers** och klistra
   in det i integrationens lösenordsfält. Både hela `Bearer …` och bara
   tokenvärdet accepteras.

Dela inte värdet eller nätverksexporter i ärenden eller chattar. Ordernummer och
behörighetsvärde sparas lokalt i Home Assistants konfigurationslagring (inte
krypterat); skydda konfigurationen och säkerhetskopiorna. Inga behörighetsvärden
finns i källkoden. Om Volvo nekar värdet visas en begäran om ny autentisering.

## Sensorer och uppdateringar

| Sensor | Innehåll |
|---|---|
| Leveransstatus | Statusens text från Volvo |
| Beräknad leverans | Volvos leveransvecka/text; rubriken finns som attribut |
| Orderändringar | Information om sista datum för ändringar; beskrivningen finns som attribut |
| Beräknad leveransvecka börjar | Måndagen i prognosveckan, om tillräckligt datumunderlag finns |
| Beräknad leveransvecka slutar | Söndagen i prognosveckan |
| Dagar till leveransveckan | Kalenderdagar till måndagen; noll från veckans start |
| Senaste leveransändring | När integrationen upptäckte ändrade leveransuppgifter |
| Senaste lyckade kontroll | När API:et senast kunde läsas |

Integrationen hämtar data när den startar och därefter **var 24:e timme** medan
sensorerna är aktiva. Detta är inte ett fast klockslag. Home Assistant kan göra
tidigare återförsök vid anslutningsfel. Du kan också uppdatera manuellt med
`homeassistant.update_entity` på en av sensorerna; alla delar samma API-anrop.

Första hämtningen skapar en baslinje och sätter ändringstidpunkten. Därefter
ändras den bara om status, leveransuppskattning (inklusive rubriken med antal
veckor), orderändringsinformation, bilbeskrivning eller bild-/modellänkar ändras. Baslinjen och
ändringstidpunkten sparas över omstarter och tas bort om integrationen raderas.
Tidpunkten avser när ändringen **upptäcktes**, inte när Volvo gjorde den.

Home Assistants Recorder visar historiken om sensorerna inte är undantagna.
Vid nätverksfel blir sensorerna otillgängliga; gammal information presenteras
inte som ny. Säljarens kontaktuppgifter hämtas i API-svaret men lagras inte av
integrationen. Långa sensorvärden kortas till 255 tecken; hela texten finns i
attributet `full_text`.

### Avisering vid ändring

Byt entitets-ID:t till din sensor för **Senaste leveransändring**. Exemplet
ignorerar första värdet samt återkomst efter omstart/anslutningsfel:

```yaml
alias: Volvo - uppdaterad leveransinformation
triggers:
  - trigger: state
    entity_id: sensor.volvo_1234567_senaste_leveransandring
conditions:
  - condition: template
    value_template: >-
      {{ trigger.from_state is not none and trigger.to_state is not none
         and trigger.from_state.state not in ['unknown', 'unavailable']
         and trigger.to_state.state not in ['unknown', 'unavailable']
         and trigger.from_state.state != trigger.to_state.state }}
actions:
  - action: persistent_notification.create
    data:
      title: Volvo leveransinformation
      message: Leveransuppgifterna har ändrats. Öppna Volvo Delivery för detaljer.
```

Inga aviseringar skapas automatiskt. Exemplet kan missa ändringar som upptäcks
under uppstart eller direkt efter ett avbrott; de finns fortfarande i sensorerna.

## Begränsningar

Endast den svenska marknaden stöds. API:et och dess behörighetsvärde är
odokumenterade och kan ändras av Volvo. Ordern måste redan kunna visas på
leveranssidan. En exakt överlämningsdag gissas aldrig; endast ett tydligt märkt
veckointervall kan räknas fram. Integrationen är inte driftsatt i din Home Assistant bara
för att filerna finns i detta repo.

## Utveckling

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest
.venv/bin/ruff check .
npm ci
npm test
npm run format:check
```

Testerna använder fiktiva orderuppgifter och gör inga anrop till Volvo.

`npm run preview` öppnar en lokal demowebbserver på `http://127.0.0.1:8765`
med fiktiva uppgifter. Den kör kortets riktiga JavaScript, men är inte en
Home Assistant-installation eller ett test mot ditt konto.
