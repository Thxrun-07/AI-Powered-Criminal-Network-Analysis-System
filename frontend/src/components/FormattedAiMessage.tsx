import React from 'react';

interface FormattedAiMessageProps {
  content: string;
  className?: string;
}

/**
 * Parses inline markdown: **bold**, `code`, and strips any stray ** asterisks
 */
export function renderInlineMarkdown(text: string): React.ReactNode[] {
  if (!text) return [];

  // Tokenize **bold**, `code`, *italic*
  const tokens: React.ReactNode[] = [];
  const regex = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      tokens.push(text.substring(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith('**') && token.endsWith('**')) {
      const inner = token.slice(2, -2);
      tokens.push(
        <strong key={`b-${match.index}`} className="font-semibold" style={{ color: 'var(--text)', fontWeight: 650 }}>
          {inner}
        </strong>
      );
    } else if (token.startsWith('`') && token.endsWith('`')) {
      const inner = token.slice(1, -1);
      tokens.push(
        <code key={`c-${match.index}`} className="mono" style={{ padding: '2px 5px', borderRadius: '4px', background: 'rgba(99, 102, 241, 0.12)', fontSize: '11px' }}>
          {inner}
        </code>
      );
    } else if (token.startsWith('*') && token.endsWith('*')) {
      const inner = token.slice(1, -1);
      tokens.push(<em key={`i-${match.index}`}>{inner}</em>);
    }
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    // Strip any lingering double asterisks if someone had unclosed **
    const remainder = text.substring(lastIndex).replace(/\*\*/g, '');
    tokens.push(remainder);
  }

  return tokens;
}

interface SectionItem {
  icon?: string;
  badgeColor?: string;
  title?: string;
  body: string;
}

function getSectionMeta(title: string): { icon: string; badgeColor: string } {
  const lower = title.toLowerCase();
  if (lower.includes('target') || lower.includes('hub') || lower.includes('kingpin') || lower.includes('suspect')) {
    return { icon: '🎯', badgeColor: 'rgba(239, 68, 68, 0.15)' };
  }
  if (lower.includes('associated') || lower.includes('operative') || lower.includes('people') || lower.includes('person')) {
    return { icon: '👥', badgeColor: 'rgba(59, 130, 246, 0.15)' };
  }
  if (lower.includes('inference') || lower.includes('analytical') || lower.includes('insight') || lower.includes('core')) {
    return { icon: '🧠', badgeColor: 'rgba(139, 92, 246, 0.15)' };
  }
  if (lower.includes('action') || lower.includes('lead') || lower.includes('warrant') || lower.includes('recommended') || lower.includes('freeze')) {
    return { icon: '🛡️', badgeColor: 'rgba(16, 185, 129, 0.15)' };
  }
  if (lower.includes('financial') || lower.includes('money') || lower.includes('bank') || lower.includes('fund') || lower.includes('flow')) {
    return { icon: '💳', badgeColor: 'rgba(16, 185, 129, 0.15)' };
  }
  if (lower.includes('telecom') || lower.includes('phone') || lower.includes('cdr') || lower.includes('call') || lower.includes('burner')) {
    return { icon: '📞', badgeColor: 'rgba(249, 115, 22, 0.15)' };
  }
  if (lower.includes('graph') || lower.includes('ecosystem') || lower.includes('topology') || lower.includes('network')) {
    return { icon: '🌐', badgeColor: 'rgba(99, 102, 241, 0.15)' };
  }
  return { icon: '📌', badgeColor: 'rgba(99, 102, 241, 0.12)' };
}

export function FormattedAiMessage({ content, className = '' }: FormattedAiMessageProps) {
  if (!content) return null;

  // Clean raw string: replace literal "\n" strings if escaped
  const normalized = content.replace(/\\n/g, '\n').trim();

  // Check if content has bullet points (• or * or - at start of lines, or inline •)
  const hasBullets = normalized.includes('•') || /(?:^|\n)\s*[-*]\s+/.test(normalized);

  if (hasBullets) {
    // Split on bullet markers
    const rawItems = normalized
      .split(/(?:\s*•\s+|\n+\s*[-*•]\s+)/)
      .map(s => s.trim())
      .filter(Boolean);

    const sections: SectionItem[] = rawItems.map(item => {
      // Check for title pattern: "**Title**: rest" or "Title: rest"
      const match = item.match(/^(?:\*\*)?([^:*]+?)(?:\*\*)?\s*:\s*([\s\S]*)$/);
      if (match) {
        const title = match[1].replace(/\*\*/g, '').trim();
        const body = match[2].trim();
        const meta = getSectionMeta(title);
        return {
          title,
          body,
          icon: meta.icon,
          badgeColor: meta.badgeColor
        };
      }
      return { body: item };
    });

    return (
      <div className={`formatted-ai-response flex flex-col gap-2.5 ${className}`} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {sections.map((sec, idx) => (
          <div
            key={idx}
            className="ai-intel-card"
            style={{
              background: 'var(--bg1)',
              border: '1px solid var(--border)',
              borderRadius: '8px',
              padding: '9px 12px',
              fontSize: '12.5px',
              lineHeight: 1.55,
              transition: 'border-color 0.2s'
            }}
          >
            {sec.title && (
              <div
                className="ai-intel-header flex items-center gap-1.5 font-bold mb-1"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontWeight: 650,
                  fontSize: '12px',
                  marginBottom: '4px'
                }}
              >
                <span>{sec.icon || '📌'}</span>
                <span
                  style={{
                    background: sec.badgeColor || 'rgba(99, 102, 241, 0.12)',
                    padding: '1px 7px',
                    borderRadius: '4px',
                    color: 'var(--text)'
                  }}
                >
                  {sec.title}
                </span>
              </div>
            )}
            <div style={{ color: 'var(--text-dim)' }}>
              {renderInlineMarkdown(sec.body)}
            </div>
          </div>
        ))}
      </div>
    );
  }

  // Otherwise, split by double newlines into standard markdown paragraphs
  const paragraphs = normalized.split(/\n\n+/).filter(Boolean);

  return (
    <div className={`formatted-ai-response flex flex-col gap-2 ${className}`} style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px', lineHeight: 1.6 }}>
      {paragraphs.map((p, idx) => (
        <div key={idx} style={{ color: 'var(--text-dim)' }}>
          {renderInlineMarkdown(p)}
        </div>
      ))}
    </div>
  );
}
