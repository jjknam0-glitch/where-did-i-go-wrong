import { PageHeader } from '../components/ui'

const SECTIONS: [string, string][] = [
  ['Photos', 'Photos are processed in memory and discarded after the check. A photo is kept only if you choose to save a problem to your history — and then only on your device, never on our servers.'],
  ['No sign-up to try', 'No name, email or age is needed to check your work.'],
  ['Your mistake profile', 'Without an account, your history and mistake profile stay in this browser’s local storage. If you create an account, they’re synced to it (without photos) so you can use another device.'],
  ['AI providers', 'Only the transcription of your handwriting uses an AI model, and only the cropped lines of math are sent. We use API settings that don’t train on submitted data where the provider offers them (commercial API data from Anthropic, Google and OpenAI is not used for training by default). Your answers are judged by our own math engine, not by an AI.'],
  ['Children under 13', 'In the US, collecting personal data from children under 13 requires verifiable parental consent (COPPA), and other countries have similar rules. Until that is handled with proper legal review, accounts are for ages 13 and up. Younger students can use everything without an account. We ask for a date of birth only to check this, and we don’t store it.'],
  ['Parent and tutor sharing', 'A share link is created by the student and can be turned off at any time. It shows patterns and progress — mistake types, topics, streaks — never photos, written work or answers.'],
  ['Transcription corrections', 'When you fix how a line was read, that correction is sent only if you turn on “Help improve handwriting reading”. It’s text only, never the photo, and it’s used only to improve recognition.'],
  ['Deleting your data', 'You can download or clear everything on this device in Account & settings, and delete your account (and everything saved to it) at any time.'],
  ['Academic integrity', 'The app never shows a final answer unless you explicitly ask, and the hint ladder makes you do the fixing. It’s a learning tool, not a homework-copying tool.'],
]

export default function Privacy() {
  return (
    <div>
      <PageHeader back title="Privacy & safety" subtitle="Many of our users are minors, so we collect only what each feature needs." />
      <div className="space-y-5">
        {SECTIONS.map(([title, body]) => (
          <section key={title}>
            <h2 className="font-semibold">{title}</h2>
            <p className="mt-1 text-[15px] leading-relaxed text-muted">{body}</p>
          </section>
        ))}
      </div>
    </div>
  )
}
