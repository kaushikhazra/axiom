import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'

// Renders assistant message bodies as markdown (#16).
//
// Raw HTML is NOT enabled: react-markdown ignores embedded HTML unless
// rehype-raw is added, and it deliberately is not. Model output is untrusted
// input -- an HTML-permitting pipeline here is an XSS sink. Do not add
// rehype-raw without a sanitiser in front of it.
//
// Typography is inherited, never imposed: theme.css sets --font-ui to
// --font-mono, so the whole app is already monospace. No highlight.js stylesheet
// is imported for exactly this reason -- those ship their own font-family and
// background and would break the dark dev-tool aesthetic. The .hljs-* colours
// live in theme.css, drawn from the existing palette.
//
// Streaming note: today the whole response arrives as ONE delta, so this always
// parses complete markdown. If real token streaming lands (#13), this component
// starts receiving partial markdown mid-parse (an unclosed fence, a half-typed
// **) and must degrade without flickering or throwing.

export default function MarkdownMessage({ text }: { text: string }) {
  return (
    <div className="markdown-body">
      <Markdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          // External links open in a new tab; noopener/noreferrer because the
          // href comes from model output.
          a: ({ ...props }) => (
            <a {...props} target="_blank" rel="noopener noreferrer" />
          ),
        }}
      >
        {text}
      </Markdown>
    </div>
  )
}
