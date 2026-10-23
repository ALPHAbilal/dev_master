export default defineBackground(() => {
  // Clicking the toolbar icon opens the side panel beside the page.
  void browser.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});
