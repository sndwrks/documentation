/**
 * Groups each depth-2 heading and everything that follows it (until the next
 * depth-2 heading) into <section class="sw-section"> so custom.css can frame
 * each h2 block as a bordered panel (sndwrks house style, matching the
 * marketing site's framed sections).
 *
 * - Only DIRECT children of the root are grouped, so headings inside asides,
 *   tabs, or JSX components never split a section.
 * - Content before the first h2 (or an entire page with no h2s) becomes a
 *   leading panel: <section class="sw-section sw-intro">.
 * - MDX ESM nodes (imports/exports) stay at the root: they render nothing
 *   and must remain top-level for the MDX compiler.
 * - Runs BEFORE Starlight's rehypeHeadingIds/anchor-link plugins (user rehype
 *   plugins precede Starlight's), so it sees plain h1/h2 elements; those
 *   later plugins visit at any depth and still find the headings.
 */

/** Headings that start a new panel (h1 in body is rare but treated like h2). */
const SECTION_START = new Set(['h1', 'h2']);

function makeSection(intro) {
	return {
		type: 'element',
		tagName: 'section',
		properties: { className: intro ? ['sw-section', 'sw-intro'] : ['sw-section'] },
		children: [],
	};
}

export default function rehypeSections() {
	return function transformer(tree, file) {
		// Only touch Starlight docs content (skip any other md/mdx the
		// processor might see, and renderMarkdown() calls with no path).
		if (!file?.path || !/[\\/]src[\\/]content[\\/]docs[\\/]/.test(file.path)) return;

		const out = [];
		let current = null;
		let sawHeading = false;

		for (const node of tree.children) {
			// Imports/exports stay at the root, outside any section.
			if (node.type === 'mdxjsEsm') {
				out.push(node);
				continue;
			}
			// Don't open an intro panel for bare whitespace between blocks.
			if (current === null && node.type === 'text' && node.value.trim() === '') {
				out.push(node);
				continue;
			}
			if (node.type === 'element' && SECTION_START.has(node.tagName)) {
				sawHeading = true;
				current = makeSection(false);
				out.push(current);
			} else if (current === null) {
				current = makeSection(!sawHeading);
				out.push(current);
			}
			current.children.push(node);
		}

		tree.children = out;
	};
}
