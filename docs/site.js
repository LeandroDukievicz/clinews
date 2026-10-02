const demo = document.querySelector('[data-screen-demo]');

if (demo) {
  const tablist = demo.querySelector('.screen-tabs');
  const tabs = [...tablist.querySelectorAll('.screen-tab')];
  const panels = [...demo.querySelectorAll('.screen-card')];

  function selectTab(selectedIndex, moveFocus = false) {
    tabs.forEach((tab, index) => {
      const selected = index === selectedIndex;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
      panels[index].hidden = !selected;
    });

    if (moveFocus) tabs[selectedIndex].focus();
  }

  tablist.setAttribute('role', 'tablist');
  tabs.forEach((tab, index) => {
    tab.setAttribute('role', 'tab');
    tab.setAttribute('aria-controls', panels[index].id);
    panels[index].setAttribute('role', 'tabpanel');
    panels[index].setAttribute('aria-labelledby', tab.id);
    panels[index].tabIndex = 0;

    tab.addEventListener('click', () => {
      demo.dataset.transition = 'true';
      selectTab(index);
    });
    tab.addEventListener('keydown', event => {
      let nextIndex;
      if (event.key === 'ArrowRight') nextIndex = (index + 1) % tabs.length;
      else if (event.key === 'ArrowLeft') nextIndex = (index - 1 + tabs.length) % tabs.length;
      else if (event.key === 'Home') nextIndex = 0;
      else if (event.key === 'End') nextIndex = tabs.length - 1;
      else return;

      event.preventDefault();
      demo.dataset.transition = 'true';
      selectTab(nextIndex, true);
    });
  });

  selectTab(0);
  demo.dataset.enhanced = 'true';
}
