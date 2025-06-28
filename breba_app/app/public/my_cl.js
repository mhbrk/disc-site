document.addEventListener(
  "click",
  function (e) {
    const target = e.target.closest("#new-chat-button");
    if (target) {
      e.stopImmediatePropagation(); // Prevents other click handlers from firing
      e.preventDefault(); // Prevents default browser action
      console.log("Click on #new-chat-button intercepted and blocked.");
    }
  },
  true // Use capture phase to intercept before other handlers
);