"""Implementation B: layered routers / services / domain.

Same HTTP contract as implementation A, radically different insides: typed
views, a `Money` value object, a coupon registry, two normalised SQL tables,
lines sorted by sku, and no debug surface at all.
"""
