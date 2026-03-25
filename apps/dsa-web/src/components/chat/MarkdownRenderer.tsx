import type React from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MarkdownRendererProps {
  content: string;
}

const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content }) => (
  <div
    className="prose prose-invert prose-sm max-w-none
      prose-headings:text-white prose-headings:font-semibold prose-headings:mt-3 prose-headings:mb-1.5
      prose-h1:text-lg prose-h2:text-base prose-h3:text-sm
      prose-p:leading-relaxed prose-p:mb-2 prose-p:last:mb-0
      prose-strong:text-white prose-strong:font-semibold
      prose-ul:my-1.5 prose-ol:my-1.5 prose-li:my-0.5
      prose-code:text-cyan prose-code:bg-white/5 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs
      prose-pre:bg-black/30 prose-pre:border prose-pre:border-white/10 prose-pre:rounded-lg prose-pre:p-3
      prose-table:w-full prose-table:text-sm
      prose-th:text-white prose-th:font-medium prose-th:border-white/20 prose-th:px-3 prose-th:py-1.5 prose-th:bg-white/5
      prose-td:border-white/10 prose-td:px-3 prose-td:py-1.5
      prose-hr:border-white/10 prose-hr:my-3
      prose-a:text-cyan prose-a:no-underline hover:prose-a:underline
      prose-blockquote:border-cyan/30 prose-blockquote:text-secondary
    "
  >
    <Markdown remarkPlugins={[remarkGfm]}>{content}</Markdown>
  </div>
);

export default MarkdownRenderer;
