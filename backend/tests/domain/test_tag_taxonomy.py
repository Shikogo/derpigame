"""How a taxonomy classifies tags: bucketing, prefixes, and what it drops.

Pure value-object tests — no Game, no app context.
"""

from dataclasses import replace

from app.domain.tag_taxonomy import DERPIBOORU_TAXONOMY, FURBOORU_TAXONOMY, TagTaxonomy


def test_a_namespaced_tag_lands_in_its_own_bucket():
    assert DERPIBOORU_TAXONOMY.bucket_for("artist:shikogo") == "artists"
    assert DERPIBOORU_TAXONOMY.bucket_for("oc:littlepip") == "ocs"
    assert DERPIBOORU_TAXONOMY.bucket_for("comic:friendship is magic") == "comics"
    assert DERPIBOORU_TAXONOMY.bucket_for("fanfic:fallout equestria") == "fanfics"
    assert DERPIBOORU_TAXONOMY.bucket_for("series:some diary") == "series"


def test_a_plain_tag_lands_in_the_goal_bucket():
    assert DERPIBOORU_TAXONOMY.bucket_for("twilight sparkle") == "tags"
    # Ships are plain tags on Derpibooru's side of the wire: the site aliases
    # bare names like "twilestia" onto ship:, so they arrive canonicalized and
    # belong in the goal bucket rather than a namespace of their own.
    assert DERPIBOORU_TAXONOMY.bucket_for("ship:twilestia") == "tags"


def test_bucket_for_takes_the_first_matching_namespace():
    # Insertion order decides overlaps, so a taxonomy can nest prefixes.
    taxonomy = TagTaxonomy(namespaces={"specific": "oc:only:", "general": "oc:"})
    assert taxonomy.bucket_for("oc:only:bob") == "specific"
    assert taxonomy.bucket_for("oc:bob") == "general"


def test_prefix_of_maps_a_bucket_back_to_its_namespace():
    assert DERPIBOORU_TAXONOMY.prefix_of("artists") == "artist:"
    assert DERPIBOORU_TAXONOMY.prefix_of("tags") == ""
    assert DERPIBOORU_TAXONOMY.prefix_of("nonsense") == ""


def test_bare_strips_a_tags_own_namespace():
    assert DERPIBOORU_TAXONOMY.bare("artist:shikogo") == "shikogo"
    assert DERPIBOORU_TAXONOMY.bare("comic:the comic") == "the comic"


def test_bare_leaves_an_unnamespaced_tag_alone():
    assert DERPIBOORU_TAXONOMY.bare("twilight sparkle") == "twilight sparkle"
    # A colon that isn't a known namespace is part of the tag, not a prefix.
    assert DERPIBOORU_TAXONOMY.bare("editor:someone") == "editor:someone"


def test_the_constant_drops_ratings_but_curates_nothing_on_its_own():
    assert DERPIBOORU_TAXONOMY.is_droppable("safe")
    assert DERPIBOORU_TAXONOMY.is_droppable("semi-grimdark")
    # Ignored tags and prefixes are curation from config.toml, so a taxonomy
    # built here ignores nothing.
    assert not DERPIBOORU_TAXONOMY.is_droppable("source needed")
    assert not DERPIBOORU_TAXONOMY.is_droppable("spoiler:the-ending")


def test_glob_curation_drops_tags_namespaces_and_families():
    curated = replace(
        DERPIBOORU_TAXONOMY,
        ignored_tags=("source needed", "spoiler:*", "editor:*", "*comments*"),
    )
    assert curated.is_droppable("source needed")  # exact
    assert curated.is_droppable("spoiler:the-ending")  # prefix / namespace
    assert curated.is_droppable("editor:someone")
    assert curated.is_droppable("adventure in the comments")  # substring family
    assert not curated.is_droppable("solo")  # a real, guessable tag
    assert not curated.is_droppable("commentary")  # a substring "comment" must not match


def test_furbooru_shares_the_scheme_but_not_semi_grimdark():
    # Furbooru is Philomena too, so it classifies by the same namespaces and drops
    # the same rating tags — except semi-grimdark, which isn't a valid Furbooru
    # rating (it aliases to an invalid tag there). Config curation lives elsewhere.
    assert FURBOORU_TAXONOMY.bucket_for("artist:kenket") == "artists"
    assert FURBOORU_TAXONOMY.bucket_for("oc:whitepaws") == "ocs"
    assert FURBOORU_TAXONOMY.bucket_for("fox") == "tags"
    assert FURBOORU_TAXONOMY.is_droppable("explicit")
    assert FURBOORU_TAXONOMY.is_droppable("grimdark")
    assert not FURBOORU_TAXONOMY.is_droppable("semi-grimdark")
    assert DERPIBOORU_TAXONOMY.is_droppable("semi-grimdark")
