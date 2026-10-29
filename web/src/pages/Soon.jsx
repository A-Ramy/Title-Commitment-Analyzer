// Screens still to come in this first slice of v2 (Analyze, Training, Knowledge, Settings).
const NAMES = { analyze: 'Analyze A Commitment', training: 'Train The Agent', knowledge: 'Knowledge', settings: 'Settings' };

export function Soon({ page }) {
  return (
    <section class="empty">
      <h3>{NAMES[page] || 'Not found'}</h3>
      <p>{NAMES[page] ? 'Coming in the next update of the new Title Agent. Use the current app for this for now.'
        : "That page doesn't exist."}</p>
    </section>
  );
}
