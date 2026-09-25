# Office reuse and review decisions

The user selected Munder Difflin's animated office and Agent Teams AI's communication graph as references. HQ now offers both views over the same data.

| Candidate | Reused | Why this scope |
|---|---|---|
| Munder Difflin c7c8921 | MIT procedural portrait renderer | Gives stable animated desk characters without shipping separately licensed art, Pixi or a competing provider scheduler. HQ floor is original SVG/CSS. |
| Agent Teams AI c2e9212 | Existing AGPL graph/avatar implementation | Better for actual reporting relationships and tasks; retained as Team map instead of rewriting a graph. |
| Ponytail e3ba2aa | MIT review skill | Reuse existing components and browser/CSS primitives; keep correctness review separate. No always-on hooks or benchmark savings claims. |
| UI/UX Pro Max dcc40ff | MIT local guidance/search skill | Targeted checks for focus, reduced motion, responsiveness, and contrast. No added animation dependency. |

The UI skill's first broad query misclassified the app as Construction/Architecture; that output was rejected. The one narrower query, `developer tools dashboard`, matched Developer Tool / IDE and dark high-contrast guidance. HQ keeps its current purple chat shell and warm office illustration; it does not blindly apply generated landing-page suggestions.

Targeted UX searches confirmed reduced motion and unobscured keyboard focus. Applied: selectable native buttons, visible focus, pause controls, current agent details resolved by ID, an accessible complete roster, no whole-page overflow at390px, clear example labeling and return-to-chat focus. The floor can pan inside its own container at small widths; roster controls offer an alternative.

Ponytail review: use existing CSS animation/SVG, existing native roster/task APIs and existing graph; avoid a new game engine, per-frame JS loops, duplicate task store, invented messages or another scheduler. This is a qualitative decision, not measured cost savings.

All pins and original licenses are retained in THIRD_PARTY_NOTICES.md and adjacent vendor/skill directories.
