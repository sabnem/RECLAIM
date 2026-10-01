// Dismiss only transient Django messages, never form errors or page content.
document.querySelectorAll('#alert-messages .alert').forEach(alert => {
  let timer;
  const pause = () => window.clearTimeout(timer);
  const schedule = () => {
    pause();
    if (document.hidden || alert.matches(':hover') || alert.contains(document.activeElement)) return;
    timer = window.setTimeout(() => {
      bootstrap.Alert.getOrCreateInstance(alert).close();
    }, 5000);
  };
  const afterFocus = () => window.setTimeout(schedule, 0);
  alert.addEventListener('mouseenter', pause);
  alert.addEventListener('mouseleave', schedule);
  alert.addEventListener('focusin', pause);
  alert.addEventListener('focusout', afterFocus);
  document.addEventListener('visibilitychange', schedule);
  alert.addEventListener('closed.bs.alert', () => {
    pause();
    document.removeEventListener('visibilitychange', schedule);
  }, {once: true});
  schedule();
});
