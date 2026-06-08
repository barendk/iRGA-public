/**
 * Goal tree expand/collapse logic.
 *
 * Two behaviours:
 *
 *   1. Per-node toggle — clicking the expand/collapse button on a tree node
 *      hides or shows that node's children div (id="children-{goal_id}").
 *      The button icon flips between expand_less (open) and expand_more (closed).
 *
 *   2. Global toggle — the #toggle-all-btn button collapses or expands every
 *      children div on the page at once, and its own label/icon reflect the
 *      current state.
 *
 * The page renders fully expanded, so the initial state is:
 *   - All children divs visible.
 *   - #toggle-all-btn reads "Alles inklappen" (data-collapsed="false").
 */

/**
 * Toggle a single node's children div.
 *
 * Called from onclick attributes in the Jinja2 template, so it must be
 * a global function (not wrapped in DOMContentLoaded).
 *
 * @param {string} childrenId  - id of the children wrapper, e.g. "children-42"
 * @param {HTMLElement} btnEl  - the expand/collapse button element
 */
function toggleChildren(childrenId, btnEl) {
    var childrenDiv = document.getElementById(childrenId);
    if (!childrenDiv) return;

    var icon = btnEl.querySelector('.material-symbols-outlined');
    var isHidden = childrenDiv.classList.contains('hidden');

    if (isHidden) {
        childrenDiv.classList.remove('hidden');
        if (icon) icon.textContent = 'expand_less';
    } else {
        childrenDiv.classList.add('hidden');
        if (icon) icon.textContent = 'expand_more';
    }
}

document.addEventListener('DOMContentLoaded', function () {
    var toggleAllBtn = document.getElementById('toggle-all-btn');
    if (!toggleAllBtn) return;

    var toggleAllLabel = document.getElementById('toggle-all-label');
    var toggleAllIcon = toggleAllBtn.querySelector('.material-symbols-outlined');

    toggleAllBtn.addEventListener('click', function () {
        var isCollapsed = toggleAllBtn.dataset.collapsed === 'true';

        // All children wrappers are identified by the id prefix set in the template.
        var allChildrenDivs = document.querySelectorAll('[id^="children-"]');

        // All per-node expand/collapse buttons use the onclick="toggleChildren(...)" pattern.
        var allNodeBtns = document.querySelectorAll('[onclick^="toggleChildren"]');

        if (isCollapsed) {
            // Expand all.
            allChildrenDivs.forEach(function (div) { div.classList.remove('hidden'); });
            allNodeBtns.forEach(function (btn) {
                var icon = btn.querySelector('.material-symbols-outlined');
                if (icon) icon.textContent = 'expand_less';
            });
            toggleAllBtn.dataset.collapsed = 'false';
            if (toggleAllIcon) toggleAllIcon.textContent = 'unfold_less';
            if (toggleAllLabel) toggleAllLabel.textContent = 'Alles inklappen';
        } else {
            // Collapse all.
            allChildrenDivs.forEach(function (div) { div.classList.add('hidden'); });
            allNodeBtns.forEach(function (btn) {
                var icon = btn.querySelector('.material-symbols-outlined');
                if (icon) icon.textContent = 'expand_more';
            });
            toggleAllBtn.dataset.collapsed = 'true';
            if (toggleAllIcon) toggleAllIcon.textContent = 'unfold_more';
            if (toggleAllLabel) toggleAllLabel.textContent = 'Alles uitklappen';
        }
    });
});
