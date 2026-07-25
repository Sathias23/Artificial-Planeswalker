/* @ds-bundle: {"format":4,"namespace":"PlaneswalkerCompanionDesignSystem_fe7895","components":[{"name":"SuggestionCard","sourcePath":"components/agent/SuggestionCard.jsx"},{"name":"AgentStatus","sourcePath":"components/core/AgentStatus.jsx"},{"name":"Badge","sourcePath":"components/core/Badge.jsx"},{"name":"Panel","sourcePath":"components/core/Panel.jsx"},{"name":"StatChip","sourcePath":"components/core/StatChip.jsx"},{"name":"CardTile","sourcePath":"components/data/CardTile.jsx"},{"name":"DeckRow","sourcePath":"components/data/DeckRow.jsx"},{"name":"ManaCost","sourcePath":"components/data/ManaCost.jsx"},{"name":"ManaCurve","sourcePath":"components/data/ManaCurve.jsx"},{"name":"ManaPip","sourcePath":"components/data/ManaPip.jsx"}],"sourceHashes":{"components/agent/SuggestionCard.jsx":"21f32d4dd005","components/core/AgentStatus.jsx":"4b1ffab7d411","components/core/Badge.jsx":"9d8acde29747","components/core/Panel.jsx":"a7a7ed9e3fd1","components/core/StatChip.jsx":"c5be43b81746","components/data/CardTile.jsx":"0c402943e776","components/data/DeckRow.jsx":"cc6987bdc9bd","components/data/ManaCost.jsx":"4acacef79327","components/data/ManaCurve.jsx":"30a178b95b11","components/data/ManaPip.jsx":"6cfe253937c4"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.PlaneswalkerCompanionDesignSystem_fe7895 = window.PlaneswalkerCompanionDesignSystem_fe7895 || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/core/AgentStatus.jsx
try { (() => {
function AgentStatus({
  state = 'idle',
  label
}) {
  const map = {
    idle: ['var(--text-tertiary)', 'Idle'],
    thinking: ['var(--accent)', 'Thinking'],
    streaming: ['var(--accent-bright)', 'Streaming']
  };
  const [color, fallback] = map[state] || map.idle;
  const pulse = state !== 'idle';
  return /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 8,
      fontFamily: 'var(--font-sans)'
    }
  }, /*#__PURE__*/React.createElement("style", null, '@keyframes apc-pulse{0%,100%{opacity:1}50%{opacity:0.35}}'), /*#__PURE__*/React.createElement("span", {
    style: {
      width: 8,
      height: 8,
      borderRadius: 999,
      background: color,
      boxShadow: pulse ? '0 0 10px var(--accent-glow), 0 0 5px ' + color : 'none',
      animation: pulse ? 'apc-pulse ' + (state === 'streaming' ? '0.9s' : '1.8s') + ' var(--ease-glide) infinite' : 'none'
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-label)',
      letterSpacing: 'var(--tracking-label)',
      textTransform: 'uppercase',
      color: pulse ? 'var(--accent)' : 'var(--text-tertiary)'
    }
  }, label || fallback));
}
Object.assign(__ds_scope, { AgentStatus });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/AgentStatus.jsx", error: String((e && e.message) || e) }); }

// components/core/Badge.jsx
try { (() => {
const tones = {
  neutral: ['var(--surface-overlay)', 'var(--text-secondary)', 'var(--border-strong)'],
  accent: ['var(--accent-glow)', 'var(--accent-bright)', 'var(--accent-dim)'],
  positive: ['rgba(95,212,160,0.12)', 'var(--positive)', 'rgba(95,212,160,0.35)'],
  negative: ['rgba(255,122,134,0.12)', 'var(--negative)', 'rgba(255,122,134,0.35)'],
  caution: ['rgba(255,194,102,0.12)', 'var(--caution)', 'rgba(255,194,102,0.35)']
};
function Badge({
  tone = 'neutral',
  children
}) {
  const [bg, fg, bd] = tones[tone] || tones.neutral;
  return /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 4,
      background: bg,
      color: fg,
      border: '1px solid ' + bd,
      borderRadius: 'var(--radius-pill)',
      padding: '2px 9px',
      font: 'var(--type-label)',
      letterSpacing: '0.04em',
      textTransform: 'uppercase',
      fontFamily: 'var(--font-sans)',
      whiteSpace: 'nowrap'
    }
  }, children);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Badge.jsx", error: String((e && e.message) || e) }); }

// components/core/Panel.jsx
try { (() => {
function Panel({
  title,
  badge,
  live = false,
  level = 'panel',
  children,
  style
}) {
  const bg = level === 'overlay' ? 'var(--surface-overlay)' : 'var(--surface-panel)';
  return /*#__PURE__*/React.createElement("section", {
    style: {
      background: bg,
      border: '1px solid var(--border-hairline)',
      borderRadius: 'var(--radius-lg)',
      boxShadow: live ? 'var(--shadow-raise)' : '0 12px 32px rgba(0,0,0,0.5)',
      overflow: 'hidden',
      fontFamily: 'var(--font-sans)',
      ...style
    }
  }, (title || badge) && /*#__PURE__*/React.createElement("header", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 'var(--space-2)',
      padding: '10px 14px',
      borderBottom: '1px solid var(--border-hairline)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-label)',
      letterSpacing: 'var(--tracking-label)',
      textTransform: 'uppercase',
      color: live ? 'var(--accent)' : 'var(--text-secondary)'
    }
  }, title), live && /*#__PURE__*/React.createElement("span", {
    style: {
      width: 6,
      height: 6,
      borderRadius: 999,
      background: 'var(--accent)',
      boxShadow: '0 0 8px var(--accent-glow), 0 0 4px var(--accent)'
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: 'auto',
      display: 'flex',
      gap: 'var(--space-1)'
    }
  }, badge)), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '12px 14px'
    }
  }, children));
}
Object.assign(__ds_scope, { Panel });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Panel.jsx", error: String((e && e.message) || e) }); }

// components/core/StatChip.jsx
try { (() => {
function StatChip({
  label,
  value,
  delta,
  style
}) {
  const dcol = delta == null ? null : String(delta).startsWith('-') ? 'var(--negative)' : 'var(--positive)';
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 2,
      background: 'var(--surface-well)',
      border: '1px solid var(--border-hairline)',
      borderRadius: 'var(--radius-md)',
      padding: '8px 12px',
      minWidth: 76,
      fontFamily: 'var(--font-sans)',
      ...style
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-micro)',
      letterSpacing: 'var(--tracking-micro)',
      textTransform: 'uppercase',
      color: 'var(--text-tertiary)'
    }
  }, label), /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      alignItems: 'baseline',
      gap: 6
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-numeric)',
      fontSize: 17,
      fontVariantNumeric: 'tabular-nums',
      color: 'var(--text-primary)'
    }
  }, value), delta != null && /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-micro)',
      fontVariantNumeric: 'tabular-nums',
      color: dcol
    }
  }, delta)));
}
Object.assign(__ds_scope, { StatChip });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/StatChip.jsx", error: String((e && e.message) || e) }); }

// components/data/CardTile.jsx
try { (() => {
function CardTile({
  name,
  art,
  width = 150,
  live = false
}) {
  const h = Math.round(width * 1.4);
  return /*#__PURE__*/React.createElement("figure", {
    style: {
      margin: 0,
      width,
      fontFamily: 'var(--font-sans)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width,
      height: h,
      borderRadius: 'var(--radius-md)',
      overflow: 'hidden',
      border: '1px solid ' + (live ? 'var(--accent-dim)' : 'var(--border-hairline)'),
      boxShadow: live ? '0 0 0 1px var(--accent-dim), 0 0 20px var(--accent-glow), 0 12px 32px rgba(0,0,0,0.5)' : '0 12px 32px rgba(0,0,0,0.5)',
      background: 'linear-gradient(160deg, var(--surface-overlay), var(--surface-well))',
      display: 'flex',
      alignItems: 'flex-end',
      transition: 'box-shadow var(--dur-2) var(--ease-glide)'
    }
  }, art ? /*#__PURE__*/React.createElement("img", {
    src: art,
    alt: name,
    style: {
      width: '100%',
      height: '100%',
      objectFit: 'cover'
    }
  }) : /*#__PURE__*/React.createElement("span", {
    style: {
      padding: 10,
      font: 'var(--type-micro)',
      letterSpacing: 'var(--tracking-micro)',
      textTransform: 'uppercase',
      color: 'var(--text-tertiary)'
    }
  }, "art — ", name)), /*#__PURE__*/React.createElement("figcaption", {
    style: {
      marginTop: 6,
      font: 'var(--type-label)',
      letterSpacing: '0.02em',
      color: 'var(--text-secondary)',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap'
    }
  }, name));
}
Object.assign(__ds_scope, { CardTile });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/CardTile.jsx", error: String((e && e.message) || e) }); }

// components/data/ManaCurve.jsx
try { (() => {
function ManaCurve({
  curve = [],
  height = 72,
  highlight = -1
}) {
  const max = Math.max(1, ...curve);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 6,
      alignItems: 'flex-end',
      height: height + 18,
      fontFamily: 'var(--font-sans)'
    }
  }, curve.map((n, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 3,
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-micro)',
      fontVariantNumeric: 'tabular-nums',
      color: i === highlight ? 'var(--accent-bright)' : 'var(--text-tertiary)'
    }
  }, n), /*#__PURE__*/React.createElement("div", {
    style: {
      width: '100%',
      maxWidth: 26,
      height: Math.max(2, Math.round(n / max * height)),
      borderRadius: 'var(--radius-sm)',
      background: i === highlight ? 'var(--accent)' : 'var(--mana-colorless)',
      opacity: i === highlight ? 1 : 0.75,
      boxShadow: i === highlight ? '0 0 12px var(--accent-glow)' : 'none',
      transition: 'height var(--dur-2) var(--ease-glide)'
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-micro)',
      color: 'var(--text-tertiary)'
    }
  }, i === curve.length - 1 ? i + '+' : i))));
}
Object.assign(__ds_scope, { ManaCurve });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/ManaCurve.jsx", error: String((e && e.message) || e) }); }

// components/data/ManaPip.jsx
try { (() => {
function ManaPip({
  color = 'colorless',
  value,
  size = 16
}) {
  const bg = 'var(--mana-' + color + ')';
  return /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      width: size,
      height: size,
      borderRadius: 999,
      background: bg,
      color: 'var(--text-inverse)',
      fontFamily: 'var(--font-sans)',
      fontWeight: 700,
      fontSize: size * 0.62,
      fontVariantNumeric: 'tabular-nums',
      lineHeight: 1,
      flex: 'none'
    }
  }, value != null ? value : '');
}
Object.assign(__ds_scope, { ManaPip });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/ManaPip.jsx", error: String((e && e.message) || e) }); }

// components/data/ManaCost.jsx
try { (() => {
function ManaCost({
  cost = '',
  size = 14
}) {
  const parts = String(cost).match(/\d+|[WUBRGC]/gi) || [];
  return /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      gap: 3,
      alignItems: 'center'
    }
  }, parts.map((p, i) => /\d/.test(p) ? /*#__PURE__*/React.createElement(__ds_scope.ManaPip, {
    key: i,
    value: p,
    size: size
  }) : /*#__PURE__*/React.createElement(__ds_scope.ManaPip, {
    key: i,
    color: p.toLowerCase() === 'c' ? 'colorless' : p.toLowerCase(),
    size: size
  })));
}
Object.assign(__ds_scope, { ManaCost });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/ManaCost.jsx", error: String((e && e.message) || e) }); }

// components/agent/SuggestionCard.jsx
try { (() => {
function SuggestionCard({
  action = 'add',
  card,
  cost,
  reason,
  confidence,
  live = false
}) {
  const tones = {
    add: 'positive',
    cut: 'negative',
    swap: 'accent'
  };
  return /*#__PURE__*/React.createElement("article", {
    style: {
      background: 'var(--surface-overlay)',
      border: '1px solid ' + (live ? 'var(--accent-dim)' : 'var(--border-hairline)'),
      borderRadius: 'var(--radius-md)',
      padding: '10px 12px',
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      boxShadow: live ? '0 0 16px var(--accent-glow)' : 'none',
      fontFamily: 'var(--font-sans)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 'var(--space-2)'
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Badge, {
    tone: tones[action] || 'neutral'
  }, action), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-body-strong)',
      color: 'var(--text-primary)'
    }
  }, card), cost && /*#__PURE__*/React.createElement(__ds_scope.ManaCost, {
    cost: cost,
    size: 12
  }), confidence != null && /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: 'auto',
      font: 'var(--type-micro)',
      fontVariantNumeric: 'tabular-nums',
      color: 'var(--text-tertiary)'
    }
  }, confidence)), reason && /*#__PURE__*/React.createElement("p", {
    style: {
      margin: 0,
      font: 'var(--type-body)',
      color: 'var(--text-secondary)'
    }
  }, reason));
}
Object.assign(__ds_scope, { SuggestionCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/agent/SuggestionCard.jsx", error: String((e && e.message) || e) }); }

// components/data/DeckRow.jsx
try { (() => {
function DeckRow({
  name,
  cost = '',
  count = 1,
  price,
  live = false
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '34px 1fr auto 64px',
      alignItems: 'center',
      gap: 'var(--space-3)',
      padding: '6px 10px',
      borderRadius: 'var(--radius-sm)',
      background: live ? 'var(--accent-glow)' : 'transparent',
      boxShadow: live ? 'inset 2px 0 0 var(--accent)' : 'none',
      fontFamily: 'var(--font-sans)',
      transition: 'background var(--dur-1) var(--ease-glide)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-numeric)',
      fontVariantNumeric: 'tabular-nums',
      color: 'var(--text-tertiary)'
    }
  }, count, "\xD7"), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-body)',
      fontWeight: live ? 700 : 400,
      color: live ? 'var(--text-primary)' : 'var(--text-secondary)',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap'
    }
  }, name), /*#__PURE__*/React.createElement(__ds_scope.ManaCost, {
    cost: cost,
    size: 13
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-numeric)',
      fontVariantNumeric: 'tabular-nums',
      color: 'var(--text-tertiary)',
      textAlign: 'right'
    }
  }, price));
}
Object.assign(__ds_scope, { DeckRow });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/DeckRow.jsx", error: String((e && e.message) || e) }); }

__ds_ns.SuggestionCard = __ds_scope.SuggestionCard;

__ds_ns.AgentStatus = __ds_scope.AgentStatus;

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.Panel = __ds_scope.Panel;

__ds_ns.StatChip = __ds_scope.StatChip;

__ds_ns.CardTile = __ds_scope.CardTile;

__ds_ns.DeckRow = __ds_scope.DeckRow;

__ds_ns.ManaCost = __ds_scope.ManaCost;

__ds_ns.ManaCurve = __ds_scope.ManaCurve;

__ds_ns.ManaPip = __ds_scope.ManaPip;

})();
