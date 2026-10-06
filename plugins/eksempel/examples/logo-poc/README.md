# Eksempel AS-logo — positiv/negativ, proof of concept

Eksempel AS er en oppdiktet organisasjon. Merket og fargene er tegnet for dette eksempelet,
slik at merkevare-pluginen kan demonstreres uten en ekte organisasjons identitet.

## Hva dette svarer på

Ett smalt spørsmål, isolert fra alt annet: **hvilken farge skal merket faktisk ha** når det
står på lys bakgrunn (positiv) vs. mørk bakgrunn (negativ)? Ikke om en logo hører hjemme i
toppfeltet, og ikke hvordan geometrien bør hentes ved byggetid på sikt — se de åpne punktene
under.

## Fargevalg

| Variant | Hex | Kilde |
|---|---|---|
| Positiv (lys bakgrunn) | `#2F5D9E` Blue | `--eksempel-blue` i `plugins/eksempel/tokens/palette.css`, primærfargen. |
| Negativ (mørk bakgrunn) | `#FFF8EE` Cream | `--eksempel-cream`, palettens verdi for tekst og logo på mørk bakgrunn. Aldri ren hvit på den mørke merkeflaten. |
| Til sammenligning | `#000000` | Uten merkefarge. |

En ekte merkevare-plugin bytter ut merket og paletten med verdier fra sin egen merkevarehåndbok,
og får bekreftet fargevalget av merkevareeieren.

## Åpne punkter — ikke løst av denne demoen

- [ ] Ingen gjenbrukbar uttrekksmekanisme bygget. Merket er limt inn i byggeskriptet, ikke
      hentet automatisk fra en pinnet kilde.
- [ ] Skal `templates/` i dette repoet i det hele tatt ha en logo? Ikke avgjort her.

## Kjør på nytt

```bash
python3 build_logo_poc_demo.py
python3 ../../../../tools/verify_standalone_core.py eksempel-logo-poc-demo.html
```
