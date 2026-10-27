# 16 — Embedding-modus sammenligning (issue #39)

Diagnoseverktøy, ikke et designmønster å kopiere videre. Bygget etter et ekte
brudd i produksjon (`en kollega-kollega/saksrom`, 15. sept. 2026, se
[issue #39](https://example.com/tun/issues/39)):
en fil viste feilaktig "ingen data funnet" åpnet via SharePoints egen innebygde
filforhåndsvisning (enkeltklikk "hurtigvisning" i dokumentbiblioteket — IKKE en
nedlasting, IKKE `/preview`-embed.aspx-vieweren som allerede er dekket av
`docs/01-tenant-constraints.md` rad 4).

## RETTELSE (samme kveld, senere) — les dette først

Denne README-en konkluderte opprinnelig med at **embedded flerlinjes
strengsammensetting** (`"tekst" + "tekst" + …` over mange linjer) var den
bekreftede årsaken. **Den konklusjonen er feil og er tilbakevist**, se rad 23 i
`docs/01-tenant-constraints.md`. En tredje, bedre isolert test (rute A og B under,
identisk innhold, kun linjeformat forskjellig) viser at BEGGE fungerer i
SharePoints forhåndsvisning. Rute B er beholdt i verktøyet nettopp for å kunne
vise dette — den er IKKE lenger merket som en risiko.

Den ekte saksfilen ble deretter strippet ned til bare sideskallet (all saksdata
fjernet) og feilet FORTSATT identisk — noe som endelig utelukket dataformat,
-innhold og -størrelse. Bisecting av selve skallet fant tre reelle, uavhengige
årsaker, dokumentert i `docs/01-tenant-constraints.md` rad 24–26 og i
`en kollega-kollega/saksrom` sin `docs/04-hosting-og-dedup.md` Trinn F–H:

1. **Bokstavelig "`<script`"-tekst i filen, selv i en HTML-kommentar som aldri
   kjøres, slår av all skriptkjøring for hele siden.** Ikke testet av dette
   verktøyet (se "Ikke i scope" under for hvorfor) — reproduser ved å legge
   teksten "`<script`" i en kommentar hvor som helst i en ellers fungerende fil.
2. **Fragment-navigasjon (`<a href="#...">`) er blokkert i samme
   forhåndsvisning**, selv om JavaScript kjører fint. CSS `:target` er derfor
   ikke en pålitelig sidebytte-mekanisme her — bruk et JavaScript-klikklytter
   (`preventDefault()` + klassebytte) i stedet.
3. **`position:sticky` og `position:fixed` er begge upålitelige** for et
   element som skal forbli synlig ved scroll (banner dekket innhold, eller
   forsvant helt, uansett hvilken av de to som ble brukt). Bruk et ikke-rullende
   app-skall (flex-kolonne, én dedikert rullende beholder) i stedet.

## Hva som faktisk ble bevist her, med tre A/B-tester mot den ekte tenanten

To konkurrerende (og feilaktige) teorier ble forkastet før den (fortsatt delvis
feilaktige) konklusjonen om flerlinjes sammensetting, ved å bygge to minimale
enkeltfelt-POC-er og teste dem direkte i SharePoints forhåndsvisning, samme
klikkevei, gjentatt:

| Test | Embedding | Dataformat | Resultat i SharePoints forhåndsvisning |
|---|---|---|---|
| POC 1 | Embedded (inline `<script>`) | Data som ÉN sammenhengende streng | ✓ Fungerte |
| POC 2 | Paired (`<script src>`) | Samme ettlinjes streng som POC 1 | ✗ Feilet — men fungerte fint åpnet direkte fra en synket OneDrive-mappe |
| Original sak | Embedded | Data bygget av ~35 linjer `"tekst" + "tekst" + …` | ✗ Feilet, identisk symptom som POC 2 |

Dette ledet til den forhastede (og feilaktige) konklusjonen om flerlinjes
sammensetting. En fjerde test — rute A og B i dette verktøyet, side om side,
identisk innhold — viste at begge fungerer. Det eneste som holder fra denne
tabellen: **paired-modus (`<script src>`) er upålitelig i denne forhåndsvisningen,
uavhengig av dataformat** — bekreftet uavhengig i offentlig dokumentasjon av
SharePoints sandkasse-CSP (`script-src 'unsafe-inline' 'unsafe-eval'` tillater
inline scripts, men blokkerer `<script src="...">`).

## De fire rutene

Alle fire viser **identisk tekstinnhold** — kun embedding-metoden og
linjeformateringen i JavaScript-en varierer, slik at forskjellen i resultat
utelukkende kan skyldes det som testes, ikke innholdet:

1. **A — Embedded, ettlinjes data.** Anbefalt mønster. `window.PANEL_A_DATA`
   satt i én sammenhengende JSON-lignende streng.
2. **B — Embedded, flerlinjes strengsammensetting.** Tidligere feilaktig merket
   som en bekreftet risiko — se rettelsen over. Beholdt i verktøyet nettopp for
   å kunne vise, på forespørsel, at den IKKE er en risiko.
3. **C — Embedded, ingen JavaScript nødvendig.** Ren statisk HTML — fungerer
   uansett hva de to andre rutene gjør. Referansepunkt: hvis denne ruta noen
   gang IKKE viser innhold, er noe fundamentalt annet galt (filen lastet ikke i
   det hele tatt).
4. **D — Paired (`<script src="./paired-data.js">`).** Krever en egen fil ved
   siden av HTML-en — kopier alltid begge sammen. Eneste rute som fortsatt er
   forventet å feile, se konklusjonen over.

## Slik brukes filen

Last `embedding-mode-comparison-poc.html` **og** `paired-data.js` opp til et
SharePoint-bibliotek (begge, samme mappe — rute D trenger sidecar-filen). Åpne
den på nøyaktig samme måte som forårsaket det opprinnelige bruddet: ett enkelt
klikk i biblioteket ("hurtigvisning"/forhåndsvisning), ikke "Åpne", ikke
nedlasting. Les av hvilke ruter som ble grønne (`✓ JavaScript kjørte, data
lastet korrekt`) og hvilke som ble stående på "Laster …" eller viste
`✗ Data IKKE lastet`.

Forventet resultat basert på funnene over: A, B og C grønne; D rød — med
mindre SharePoints prosesseringsvei har endret seg siden 15. sept. 2026, i så
fall er det verdt å oppdatere `docs/01-tenant-constraints.md` med et nytt funn.

**Denne siden tester IKKE** de tre nye funnene fra rettelsen over (stray
"`<script`"-tekst, fragment-navigasjon, sticky/fixed) — den er ikke bygget om
til det, se "Ikke i scope".

## Gjenoppbygging

```bash
python3 examples/16-embedding-mode-comparison-poc/build_embedding_comparison_poc.py
```

Genererer `embedding-mode-comparison-poc.html` og `paired-data.js`. Ikke rediger
`.html`-filen for hånd — samme regel som resten av `examples/`.

## Ikke i scope

- Ingen forsøk på å automatisere selve SharePoint-testen (samme begrunnelse som
  rad 19/22 i `docs/01-tenant-constraints.md`: det finnes ingen automatiserbar
  fasit for en ekte SharePoint-forhåndsvisning i en ekte tenant — noen må se på
  det, i den ekte konteksten).
- Ingen utvidelse av DENNE siden til å også teste de tre nye funnene (rad
  24–26) — de har en annen karakter (tekstskanning, navigasjon, CSS-layout, ikke
  embedding-modus) og ble testet med egne, engangs minimale reproduksjoner
  direkte i `en kollega-kollega/saksrom` sin sak, ikke bygget som permanente
  eksempler her. Vurder et eget `examples/17-...` hvis dette blir et
  tilbakevendende behov.
- `tools/verify_standalone_core.py` (det generiske kjerneverktøyet i dette
  repoet) har derimot fått en permanent, automatisert sjekk for funn #1
  (`check_no_stray_script_text()`) — den er generisk nok til å høre hjemme der,
  i motsetning til denne siden som er et engangs sammenligningsverktøy for
  embedding-modus spesifikt.

## Bevisst holdt åpen — ikke en avsluttet sak

Rad 23–26 samlet representerer den STØRSTE enkeltrunden med nye, bekreftede
funn om organisasjonens SharePoint-tenant siden dette repoet startet — og en av dem (rad
23) var en feilslutning før den ble rettet samme kveld. Det mønsteret i seg
selv er en advarsel: konklusjonene i `docs/01-tenant-constraints.md` er basert
på det som er testet SÅ LANGT, i de kombinasjonene av visningsflate/enhet/
delingsvei som noen tilfeldigvis har støtt på gjennom et ekte brudd. Det er
ingen grunn til å anta at listen er uttømmende — snarere motsatt, se hvor fort
den vokste denne ene kvelden alene.

Konkret følger av dette:

- **Anta at det finnes flere spesialtilfeller vi ennå ikke har støtt på.** Et
  saksrom, dashboard eller annet standalone-verktøy som "virker i dag" har
  bare blitt testet mot de konkrete forholdene det faktisk har blitt åpnet
  under — ikke mot SharePoints fulle, udokumenterte oppførsel.
- **Dette er, på lengre sikt, en relevant sak for organisasjonens sikkerhetsavdeling** —
  ikke fordi noe av det som er funnet her er et sikkerhetsbrudd i seg selv, men
  fordi flere av funnene (særlig rad 25: en naiv tekstskanning som slår av all
  skriptkjøring basert på bokstavelig "`<script`"-tekst, selv i en kommentar)
  peker mot et innholds-/sikkerhetsskanningslag foran SharePoints forhånds-
  visning hvis eksakte regler ikke er dokumentert noe sted vi har tilgang til.
  Å forstå det laget bedre — helst fra noen som faktisk eier eller konfigurerer
  det — ville gjort fremtidig feilsøking i dette repoet og i saksrom-familien
  raskere og mer presist enn gjentatt bisecting fra utsiden.
- Denne README-en og `docs/01-tenant-constraints.md` oppdateres videre etter
  hvert som flere reelle brudd dukker opp — det er poenget med tabellformatet,
  inkludert å beholde tilbakeviste rader synlig i stedet for å slette dem.
