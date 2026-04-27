# Exporting Data

`ctl list <resource> --limit 1000 --format json > out.json` is the
canonical export. YAML works but is slower to parse downstream.
