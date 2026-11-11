# Archive

Closed items are filed here, newest last. Each one goes under its own number.

## 1. Markdown front matter

Pages now carry their title, date and draft flag in a TOML block between two
`+++` lines at the top of the file.

- 1-1, Parse the front matter: done. A malformed block stops the build and
  names the page.
- 1-2, Use the title and date in templates: done. A draft page is left out of
  the build and of the index.

The section's done line was met: a page's title and date come from its front
matter, a draft is not built, and a page without front matter builds as before.
