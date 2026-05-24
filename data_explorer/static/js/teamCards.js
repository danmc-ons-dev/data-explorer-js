sessionStorage.removeItem("tabno");

// Scroll the meet-the-team card row by one card when the arrow is clicked.
document.querySelectorAll('[data-js="ons-team-cards"]').forEach((container) => {
  const list = container.querySelector('[data-js="ons-team-cards-list"]');
  const nextButton = container.querySelector('[data-js="ons-team-cards-next"]');

  if (!list || !nextButton) {
    return;
  }

  const getScrollAmount = () => {
    const firstItem = list.querySelector("li");
    if (!firstItem) {
      return 0;
    }

    const itemWidth = firstItem.getBoundingClientRect().width;
    const styles = window.getComputedStyle(list);
    const gapValue = styles.columnGap || styles.gap || "0";
    const gap = Number.parseFloat(gapValue) || 0;

    return itemWidth + gap;
  };

  nextButton.addEventListener("click", () => {
    const maxScrollLeft = list.scrollWidth - list.clientWidth;
    const scrollAmount = getScrollAmount();

    if (scrollAmount === 0) {
      return;
    }

    if (list.scrollLeft >= maxScrollLeft - 1) {
      list.scrollTo({ left: 0, behavior: "smooth" });
      return;
    }

    list.scrollBy({ left: scrollAmount, behavior: "smooth" });
  });
});
