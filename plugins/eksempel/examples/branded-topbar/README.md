# Eksempel AS-brandet topbar — hamburger, logo (negativ), info- og fullskjerm-ikon

Det nøytrale topbar-mønsteret fra `examples/07-topbar-pattern-demo/` med merkevare på: logo,
farger og ikoner. Eksempel AS er en oppdiktet organisasjon. Merket, fargene og ikonene er
tegnet for dette eksempelet.

## Hva dette svarer på

Kan de tre emoji-knappene fra `examples/07-topbar-pattern-demo/` (`☰`, `ℹ️`, `⛶`) byttes med
ekte SVG-ikoner, farget etter samme "negativ"-regel som logoen — og holder det, praktisk, for
et helt sett av ikoner og ikke bare én logo?

## Hva som er målt, ikke antatt

- Ikonene (`hamburger`, `info`, `fullscreen`, `fullscreen-exit`) er tegnet for dette
  eksempelet: `viewBox 0 0 16 16`, strekbredde 1,5, runde ender.
- Hvert ikon bærer sin egen `viewBox` ved siden av path-dataen. Et tidligere byggeskript
  hardkodet én felles viewBox og klippet et ikon med større lerret — funnet ved pikselmåling i
  en ekte nettleser, ikke ved øyemål. Mønsteret er beholdt så feilen ikke kan komme tilbake.
- Bakgrunnsfarge `#1B2A4A` Navy (`--eksempel-navy`).
- Kontrast `#FFF8EE` mot `#1B2A4A` = 13,49:1, mot WCAG 2.2s 3:1-krav for ikoner. Målt, ikke
  antatt trygt.
- `fullscreen-exit` er speilvendingen av `fullscreen`: samme hjørner, pilene peker innover.
  Byttes inn/ut via `aria-pressed`, synkronisert mot `fullscreenchange` (fanger Escape-tasten,
  ikke bare knappeklikk).

## Fargevalg og spacing — hva er bekreftet, hva er gjetning

| Element | Verdi | Status |
|---|---|---|
| Bakgrunn | `#1B2A4A` Navy | Fra pluginens palett |
| Logo/ikon-farge | `#FFF8EE` Cream | Samme regel som logoen |
| Logo-klaring | 4px | Ingen regel, en oppdiktet merkevare har ingen. Knyttet til repoets 8px-grid. En ekte merkevare-plugin bruker regelen fra sin egen merkevarehåndbok |

## Åpne punkter — ikke løst av denne demoen

- [ ] Logo-klaring er en gjetning, ikke en regel.
- [ ] Kun disse tre knappene er byttet — resten av topbar-mønsteret (meny-panel,
      info-panel-innhold) er urørt.
- [ ] Beslutning om `templates/` skal arve dette mønsteret er ikke tatt.
- [ ] Android/ekte Teams-lenke ikke re-testet mot denne versjonen.

## Kjør på nytt

```bash
python3 build_branded_topbar_demo.py
python3 ../../../../tools/verify_standalone_core.py eksempel-branded-topbar-demo.html
```
