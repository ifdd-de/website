# ifdd-de/website

Source of the website [ifdd.de](https://ifdd.de): the first address for anyone
who wants to know what IFDD (Integration of Federated Data Domains) is, what the
names under `example.ifdd.de` mean, and where the repositories and Python
packages of the `ifdd-de` organisation are.

The site is plain HTML and one stylesheet, in English and German. No build
step, no JavaScript, no cookies, nothing loaded from other hosts. It is served
by the upstream unprivileged nginx image; this repository builds no image.

## Layout

| Path | Contents |
| --- | --- |
| `site/` | The pages: English at `/`, German at `/de/` with the same paths, `404.html`, `assets/` |
| `legal.example/` | Templates of the German legal pages `/impressum/` and `/datenschutz/` |
| `legal/` | The real legal pages, **not in Git** (see below) |
| `nginx/default.conf` | Server configuration, including the redirects of `www.ifdd.de` and `example.ifdd.de` |
| `compose.yml` | The container |
| `tests/check_site.py` | Static checks, standard library only |
| `tests/smoke.sh` | Checks a running server over HTTP |

## Run

```bash
git clone https://github.com/ifdd-de/website.git
cd website
cp -r legal.example legal      # then fill in legal/*.html, see below
docker compose up -d
```

The container publishes plain HTTP on `127.0.0.1:8080`. To change the address,
copy `dotenv.dist` to `.env` and set `IFDD_WEBSITE_BIND` and `IFDD_WEBSITE_PORT`.
Compose stops with "bind source path does not exist" if `legal/` is missing.

Content changes (`site/`, `legal/`) are live immediately: `git pull` is enough.
Changes to `nginx/default.conf` need `docker compose restart`.

## TLS endpoint and DNS

TLS is not part of this repository. An endpoint in front of the container must

- terminate TLS for `ifdd.de`, `www.ifdd.de` and `example.ifdd.de`, and
- forward all three to the container, keeping the original `Host` header.

nginx then answers by host:

| Host | Response |
| --- | --- |
| `ifdd.de` | the site |
| `www.ifdd.de` | `301` to `https://ifdd.de` with the same path and query |
| `example.ifdd.de` | `302` to `https://ifdd.de/example/` (`302`: browsers keep a `301` forever) |
| any other host | the site (default server) |

DNS needs records for these three names only. Demo nodes under
`<node>.grid.example.ifdd.de` get records of their own if they ever exist; the
reservation of `example.ifdd.de` is decision 0002 in `ifdd-de/overview`.

## Legal pages

The Impressum and the privacy policy contain personal data (name, address) and
are usually produced by a generator whose terms apply to the text. They are
therefore kept out of this public repository:

1. `cp -r legal.example legal`
2. Replace the placeholder block in `legal/impressum.html` and
   `legal/datenschutz.html` with the generated text. Keep the page frame.
3. Keep `legal/` on the server (and in a backup); `.gitignore` excludes it.

The privacy policy should mention that the TLS endpoint and nginx may log IP
addresses; nginx in this container logs requests to the container log.

## Editing

- Every page exists in both languages with the same path (`site/x/` and
  `site/de/x/`) and links to its counterpart with `hreflang`.
- Links between pages are relative (`../packages/`), so the pages also work
  from a local folder. `404.html` and the legal pages are the exception: they
  are served under other paths and use links from the site root.
- No scripts, no inline styles, no resources from other hosts.
- Run the checks before a commit:

```bash
python tests/check_site.py
```

`tests/check_site.py` needs Python 3.9 or newer and nothing else. With a running
container, `tests/smoke.sh [BASE_URL]` checks status codes, redirects, the 404
page and the legal pages. Both run in CI (`.github/workflows/ci.yml`).

## AI assistance

Parts of this repository, especially the tests and the page texts, were
developed or improved with the help of large language models. The maintainer
reviewed and approved all changes.

## License

BSD-3-Clause, see [LICENSE](LICENSE). The logo files in `site/assets/` come
from `ifdd-de/overview` (same license). The mark is drawn from glyphs of
Archivo Black (SIL Open Font License); no font file is shipped. The legal pages
in `legal/` are not covered by this license.
