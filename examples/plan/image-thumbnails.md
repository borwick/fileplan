+++
title = "Image thumbnails"
sub-phase = "2-1"
position = 200
number = 2
+++

Photo pages load slowly because every image is served at full size. Make a
smaller copy of each image when the site is built, and have pages show the
small copy with a link to the original.

**Done when** every image has a thumbnail after a build, pages show the
thumbnail and link to the full image, and an unchanged image is not resized
again.

### Sub-phases
- **2-1 — Resize images at build time** **done** Thumbnails are 400 pixels wide unless the site's settings say otherwise.
  Write a thumbnail of each image beside the built pages, no wider than a width
  set in the site's settings.
  *Done when* every image in the site has a thumbnail after a build.
- **2-2 — Show thumbnails in pages**
  Point each image on a page at its thumbnail, and wrap it in a link to the full
  image.
  *Done when* a built page shows the thumbnail, and clicking it opens the
  original.
- **2-3 — Skip images that have not changed**
  Keep each image's checksum from the last build, and resize only the images
  whose checksum has changed.
  *Done when* a second build with no changed images resizes nothing.
