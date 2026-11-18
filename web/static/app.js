const state = { view: 'variants', variantId: null, automaticId: null, number: 1,
  variants: [], automaticVariants: [], options: [], picks: {}, editingEnabled: false };
const editorState = { problem: null, field: null, anchor: null };
const byId = id => document.getElementById(id);
const plural = (count, one, few, many) => {
  const last = count % 10, lastTwo = count % 100;
  return count + ' ' + (lastTwo >= 11 && lastTwo <= 14 ? many : last === 1 ? one : last >= 2 && last <= 4 ? few : many);
};

function node(tag, className = '', text = '') {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text) el.textContent = text;
  return el;
}

function copyIcon() {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('aria-hidden', 'true');
  const outline = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
  outline.setAttribute('x', '8');
  outline.setAttribute('y', '8');
  outline.setAttribute('width', '12');
  outline.setAttribute('height', '12');
  outline.setAttribute('rx', '2');
  const back = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  back.setAttribute('d', 'M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2');
  svg.append(outline, back);
  return svg;
}

async function copyText(value) {
  value = value.replace(/\[\[formula:([0-9a-f]{64}):\d+:\d+\]\]/g,
    (_, sha) => `![Формула из исходного документа](${location.origin}/formulas/${sha.slice(0, 2)}/${sha}.png)`);
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value);
      return;
    } catch (_) { /* Older browsers can still support the selection fallback. */ }
  }
  const field = node('textarea');
  field.value = value;
  field.style.position = 'fixed';
  field.style.opacity = '0';
  document.body.append(field);
  field.select();
  const copied = document.execCommand('copy');
  field.remove();
  if (!copied) throw new Error('Копирование текста недоступно');
}

async function pngFromAsset(asset) {
  const response = await fetch(asset.url);
  if (!response.ok) throw new Error(`Не удалось загрузить рисунок: ${response.status}`);
  const blob = await response.blob();
  if (blob.type === 'image/png') return blob;
  const bitmap = await createImageBitmap(blob);
  const canvas = document.createElement('canvas');
  canvas.width = bitmap.width;
  canvas.height = bitmap.height;
  canvas.getContext('2d').drawImage(bitmap, 0, 0);
  bitmap.close();
  const png = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
  if (!png) throw new Error('Не удалось подготовить рисунок');
  return png;
}

function copyImage(asset) {
  if (!navigator.clipboard?.write || !window.ClipboardItem) {
    throw new Error('Копирование рисунков недоступно в этом браузере');
  }
  return navigator.clipboard.write([
    new ClipboardItem({ 'image/png': pngFromAsset(asset) })
  ]);
}

function copyButton(label, caption, value, type = 'text') {
  const button = node('button', 'copy-button');
  button.type = 'button';
  button.title = label;
  button.setAttribute('aria-label', label);
  button.append(copyIcon(), node('span', 'copy-button-label', caption));
  button.addEventListener('click', async event => {
    event.stopPropagation();
    button.disabled = true;
    const labelNode = button.querySelector('.copy-button-label');
    labelNode.textContent = 'Копирую…';
    try {
      if (type === 'image') await copyImage(value);
      else await copyText(value);
      button.classList.add('is-success');
      labelNode.textContent = 'Скопировано';
      button.setAttribute('aria-label', `${label}: скопировано`);
    } catch (error) {
      button.classList.add('is-error');
      labelNode.textContent = 'Не удалось';
      button.title = error.message;
      button.setAttribute('aria-label', `${label}: ${error.message}`);
    } finally {
      button.disabled = false;
      clearTimeout(button.copyResetTimer);
      button.copyResetTimer = setTimeout(() => {
        button.classList.remove('is-success', 'is-error');
        labelNode.textContent = caption;
        button.title = label;
        button.setAttribute('aria-label', label);
      }, 2200);
    }
  });
  return button;
}

function editLatexButton(problem, field) {
  const button = node('button', 'copy-button edit-latex-button', 'Править LaTeX');
  button.type = 'button';
  const subject = { statement: 'условия', answer: 'ответа', answer_field: 'поля ответа',
    answer_table: 'таблицы ответа', solution: 'решения' }[field];
  button.title = `Править код ${subject}`;
  button.addEventListener('click', event => {
    event.stopPropagation();
    openLatexEditor(problem, field);
  });
  return button;
}

function renderLatexEditorPreview() {
  const preview = byId('latex-editor-preview');
  preview.replaceChildren();
  const value = byId('latex-editor-text').value.trim();
  if (!value) {
    preview.append(node('p', 'criteria-note', 'Предпросмотр появится после ввода текста.'));
    return;
  }
  if (editorState.field === 'answer_field') {
    const field = parseAnswerFieldTemplate(value, editorState.problem.answer_field?.kind);
    if (!field) {
      preview.append(node('p', 'criteria-note', 'Оставьте в строке место для ответа: _____'));
      return;
    }
    preview.append(renderAnswerField({ answer_field: field }));
    return;
  }
  if (editorState.field === 'answer_table') {
    const labels = parseAnswerTableLabels(value);
    if (!labels) {
      preview.append(node('p', 'criteria-note', 'Укажите от двух до шести подписей, каждую с новой строки.'));
      return;
    }
    preview.append(renderResponseTable({ answer_field: { kind: 'table', labels } }));
    return;
  }
  renderStatement(preview, value,
    editorState.field === 'statement' ? editorState.problem.response_labels : null);
}

function openLatexEditor(problem, field) {
  editorState.problem = problem;
  editorState.field = field;
  editorState.anchor = problem.id;
  const name = { statement: 'условие', answer: 'ответ', answer_field: 'поле ответа',
    answer_table: 'таблица ответа', solution: 'решение' }[field];
  byId('latex-editor-title').textContent = `Задание ${problem.problem_number}: ${name}`;
  byId('latex-editor-text').value = field === 'answer_field' ? answerFieldTemplate(problem)
    : field === 'answer_table' ? answerTableLabels(problem).join('\n') : (problem[field] || '');
  byId('latex-editor-help').textContent = field === 'answer_field'
    ? 'Сохраните слово «Ответ:» и обозначьте каждое место для записи несколькими знаками подчёркивания. Подписи могут содержать \\(...\\).'
    : field === 'answer_table'
      ? 'Каждая строка — подпись одного столбца. Для формул используйте \\(...\\); пустая строка ответа добавляется автоматически.'
      : 'Используйте \\(...\\) для формул и сохраняйте структуру таблиц LaTeX.';
  byId('latex-editor-status').textContent = '';
  renderLatexEditorPreview();
  const dialog = byId('latex-editor');
  dialog.showModal();
  byId('latex-editor-text').focus();
}

async function saveLatexEdit() {
  const value = byId('latex-editor-text').value.trim();
  const status = byId('latex-editor-status');
  const save = byId('latex-editor-save');
  if (!value) {
    status.textContent = 'Пустой текст сохранить нельзя.';
    status.className = 'latex-editor-status is-error';
    return;
  }
  save.disabled = true;
  status.textContent = 'Сохраняю…';
  status.className = 'latex-editor-status';
  try {
    const response = await fetch(`/api/problems/${encodeURIComponent(editorState.problem.id)}/text`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ field: editorState.field, value }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
    const anchor = editorState.anchor;
    byId('latex-editor').close();
    await update();
    document.querySelector(`[id$="-${CSS.escape(anchor)}"]`)?.scrollIntoView({ block: 'center' });
  } catch (error) {
    status.textContent = `Не удалось сохранить: ${error.message}`;
    status.className = 'latex-editor-status is-error';
  } finally {
    save.disabled = false;
  }
}

function labelForStatus(verdict) {
  return verdict === 'yes' ? 'Подходит для 2027' :
         verdict === 'no' ? 'Не подходит для 2027' :
         verdict === 'partial' ? 'Частично подходит' : 'Не оценено';
}

function renderCorrespondence(problems, variant) {
  const host = byId('correspondence');
  host.replaceChildren();
  host.hidden = true;
  if (state.view !== 'variants' || ![2022, 2023].includes(variant?.exam_year) || !problems.length) return;

  const panel = node('section', 'correspondence-panel panel');
  panel.append(node('h3', '', `Соответствие номеров: ${variant.exam_year} → 2027`));
  panel.append(node('p', 'correspondence-intro',
    'Позиция 2027 определяется по теме, формату ответа и баллам. Для неподходящих задач показан ближайший проверенный кандидат; в каталог 2027 они не включены.'));
  const scroll = node('div', 'correspondence-scroll');
  const table = node('table', 'correspondence-table');
  const head = node('thead');
  const headings = node('tr');
  for (const label of [`№ ${variant.exam_year}`, '№ 2027 / кандидат', 'Оценка', 'Основание']) {
    headings.append(node('th', '', label));
  }
  head.append(headings);
  table.append(head);
  const body = node('tbody');
  for (const problem of problems) {
    const row = node('tr');
    const source = node('td');
    const link = node('a', 'correspondence-task-link', String(problem.problem_number));
    link.href = `#task-${problem.problem_number}-${problem.id}`;
    source.append(link);
    row.append(source);
    row.append(node('td', problem.verdict === 'no' ? 'candidate-position' : '',
      problem.target_problem_number ? String(problem.target_problem_number) : '—'));
    const verdict = node('td');
    verdict.append(node('span', `problem-state ${problem.verdict || 'unassessed'}`,
      labelForStatus(problem.verdict)));
    row.append(verdict);
    row.append(node('td', 'correspondence-reason', problem.verdict === 'yes'
      ? 'Тема, формат и баллы соответствуют.' : problem.relevance_reason || 'Основание не указано.'));
    body.append(row);
  }
  table.append(body);
  scroll.append(table);
  panel.append(scroll);
  host.append(panel);
  host.hidden = false;
}

function topicLabel(topic) {
  return ({ mechanics: 'Механика', molecular: 'Молекулярная физика',
    electrodynamics: 'Электродинамика', quantum: 'Квантовая физика',
    cross_topic: 'Общие вопросы и эксперимент' })[topic] || topic;
}

function variantDisplayTitle(variant) {
  return variant.is_official_demo || variant.exam_year === 2027
    || /^ЕГЭ 202[56] —/.test(variant.title || variant.variant_title || '')
    ? (variant.title || variant.variant_title)
    : `Демидова ${variant.exam_year}-${variant.variant_number}`;
}

function automaticBaseTitle(variant) {
  return variant.base_is_official_demo ? variant.base_title :
    `Демидова ${variant.base_year}-${variant.base_variant_number}`;
}

function cleanLatex(value) {
  return value.replaceAll('\\&', '&').replaceAll('\\%', '%')
    .replaceAll('\\_', '_').replaceAll('\\#', '#').trim();
}

function renderMathInto(container, value) {
  const rx = /\\\(([\s\S]*?)\\\)|\\\[([\s\S]*?)\\\]|\[\[formula:([0-9a-f]{64}):(\d+):(\d+)\]\]/g;
  let cursor = 0;
  for (const match of value.matchAll(rx)) {
    if (match.index > cursor) container.append(document.createTextNode(value.slice(cursor, match.index)));
    if (match[3]) {
      const img = node('img', 'inline-formula');
      img.src = `/formulas/${match[3].slice(0, 2)}/${match[3]}.png`;
      img.alt = 'Формула из исходного документа';
      img.loading = 'lazy';
      img.width = Math.min(600, Math.max(20, Math.round(Number(match[4]) * 1.5)));
      container.append(img);
      cursor = match.index + match[0].length;
      continue;
    }
    const display = match[2] !== undefined;
    const math = node(display ? 'div' : 'span', display ? 'math-expression math-display' : 'math-expression');
    if (window.PhysEgeMath) {
      window.PhysEgeMath.render(math, match[1] ?? match[2], display);
    } else {
      math.textContent = match[1] ?? match[2];
    }
    container.append(math);
    cursor = match.index + match[0].length;
  }
  if (cursor < value.length) container.append(document.createTextNode(value.slice(cursor)));
}

function latexTableRows(body) {
  return body.replace(/\\hline\b/g, '')
    .split(/\\\\\s*(?:\r?\n|$)/).map(row => row.trim()).filter(Boolean);
}

function renderStatement(container, text, responseLabels = null) {
  const rx = /\\begin\{tabular\}\{[^}]*\}([\s\S]*?)\\end\{tabular\}/g;
  let cursor = 0;
  for (const match of text.matchAll(rx)) {
    if (match.index > cursor) {
      renderProse(container, text.slice(cursor, match.index));
    }
    const wrap = node('div', 'latex-table-wrap');
    const table = node('table', 'latex-table');
    const rows = latexTableRows(match[1]);
    if (responseLabels?.length === 2 && rows.length === 1 &&
        rows[0].split(/(?<!\\)&/).length === 2) {
      cursor = match.index + match[0].length;
      continue;
    }
    for (const row of rows) {
      if (!row.trim()) continue;
      const tr = node('tr');
      for (const cell of row.split(/(?<!\\)&/)) {
        const td = node('td');
        renderMathInto(td, cleanLatex(cell));
        tr.append(td);
      }
      table.append(tr);
    }
    wrap.append(table);
    container.append(wrap);
    cursor = match.index + match[0].length;
  }
  if (cursor < text.length) {
    renderProse(container, text.slice(cursor));
  }
}

function answerTableLabels(problem) {
  if (!problem.answer_table_labels && matchingLayout(problem)?.answerLabels) {
    return matchingLayout(problem).answerLabels;
  }
  return problem.answer_field?.kind === 'table'
    ? problem.answer_field.labels
    : problem.response_labels;
}

function parseAnswerTableLabels(value) {
  const labels = value.split(/\r?\n/).map(label => label.trim()).filter(Boolean);
  return labels.length >= 2 && labels.length <= 6 && labels.every(label => label.length <= 500)
    ? labels : null;
}

function answerFieldTemplate(problem) {
  const field = problem.answer_field;
  if (!field || field.kind === 'table' || field.kind === 'boxes') return '';
  const parts = ['Ответ:'];
  if (field.prefix) parts.push(field.prefix);
  parts.push('____________');
  if (field.kind === 'pair') parts.push('±', '____________');
  if (field.unit) parts.push(field.unit);
  return parts.join(' ');
}

function parseAnswerFieldTemplate(value, kind = 'line') {
  const payload = value.replace(/^\s*Ответ\s*:?\s*/i, '');
  const blanks = [...payload.matchAll(/_{3,}|…{3,}/g)];
  if (!blanks.length) return null;
  if (kind === 'pair' && (blanks.length < 2 || !/(?:±|\\pm|\+-)/.test(payload))) return null;
  return {
    kind: kind === 'pair' ? 'pair' : 'line',
    prefix: payload.slice(0, blanks[0].index).trim(),
    unit: payload.slice(blanks.at(-1).index + blanks.at(-1)[0].length).trim().replace(/[.;]+$/, ''),
  };
}

function renderResponseTable(problem, editable = false) {
  const labels = answerTableLabels(problem);
  if (!Array.isArray(labels) || labels.length < 2) return null;
  const block = node('div', 'response-table-block');
  const compact = labels.every((label, index) => label === 'АБВ'[index]);
  const table = node('table', `response-table${compact ? ' is-compact' : ''}`);
  table.setAttribute('aria-label', 'Таблица для записи ответа');
  const head = node('tr');
  for (const label of labels) {
    const th = node('th');
    renderMathInto(th, cleanLatex(label));
    head.append(th);
  }
  const fields = node('tr', 'response-table-fields');
  for (const label of labels) {
    const cell = node('td');
    cell.setAttribute('aria-label', `Ответ для «${cleanLatex(label)}»`);
    fields.append(cell);
  }
  table.append(head, fields);
  block.append(table);
  if (editable && state.editingEnabled) block.append(editLatexButton(problem, 'answer_table'));
  return block;
}

function renderAnswerField(problem, editable = false) {
  const field = problem.answer_field;
  if (!field || field.kind === 'table') return null;
  const block = node('div', `answer-field answer-field-${field.kind}`);
  block.setAttribute('aria-label', 'Поле для записи ответа');
  const input = node('span', 'answer-field-input');
  input.append(node('span', 'answer-field-label', 'Ответ:'));
  block.append(input);
  if (field.kind === 'boxes') {
    const boxes = node('span', 'answer-boxes');
    for (let index = 0; index < (field.count || 2); index++) {
      boxes.append(node('span', 'answer-box'));
    }
    input.append(boxes);
    return block;
  }
  if (field.prefix) {
    const prefix = node('span', 'answer-prefix');
    renderMathInto(prefix, field.prefix);
    input.append(prefix);
  }
  input.append(node('span', 'answer-blank'));
  if (field.kind === 'pair') {
    input.append(node('span', 'answer-plus-minus', '±'), node('span', 'answer-blank answer-blank-pair'));
  }
  if (field.unit) {
    const unit = node('span', 'answer-unit');
    renderMathInto(unit, field.unit);
    input.append(unit);
    if (window.PhysEgeMath?.renderer === 'mathjax' && unit.querySelector('.math-expression')) {
      // STIX Two Cyrillic mtext can paint outside a zero-width MathJax box.
      // Reserve the painted width before placing the adjacent editor button.
      const observer = new MutationObserver(() => {
        if (unit.querySelector('.is-math-pending')) return;
        observer.disconnect();
        unit.style.minWidth = '0px';
        unit.style.minWidth = `${Math.ceil(unit.scrollWidth) + 2}px`;
      });
      observer.observe(unit, { attributes: true, childList: true, subtree: true });
    }
  }
  if (editable && state.editingEnabled && field.kind !== 'boxes') {
    block.append(editLatexButton(problem, 'answer_field'));
  }
  return block;
}

function statementForCopy(problem) {
  const source = matchingInstructionBeforeChoices(problem.statement || 'Условие не извлечено.');
  const labels = answerTableLabels(problem);
  if (!Array.isArray(labels) || labels.length < 2) return source;
  const sourceLabels = problem.response_labels;
  const tableRx = /\\begin\{tabular\}\{[^}]*\}([\s\S]*?)\\end\{tabular\}/g;
  const statement = source.replace(tableRx, (whole, body) => {
    const rows = latexTableRows(body);
    return sourceLabels?.length === 2 && sourceLabels.every((label, index) => label === labels[index]) &&
      rows.length === 1 &&
      rows[0].split(/(?<!\\)&/).length === 2 ? '' : whole;
  }).trim();
  const rowEnd = '\\\\';
  const table = [
    `\\begin{tabular}{|${labels.map(() => 'c').join('|')}|}`,
    '\\hline',
    `${labels.join(' & ')} ${rowEnd}`,
    '\\hline',
    `${labels.map(() => ' ').join(' & ')} ${rowEnd}`,
    '\\hline',
    '\\end{tabular}',
  ].join('\n');
  return `${statement}\n\n${table}`;
}

function renderProse(container, text) {
  const lines = text.trim().split(/\n/);
  let list = null;
  let paragraph = [];
  const flushParagraph = () => {
    if (!paragraph.length) return;
    const el = node('p');
    renderMathInto(el, paragraph.join(' ').trim());
    container.append(el);
    paragraph = [];
  };
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) { flushParagraph(); list = null; continue; }
    if (line.startsWith('\\[') && line.endsWith('\\]')) {
      flushParagraph();
      list = null;
      renderMathInto(container, line);
      continue;
    }
    const item = line.match(/^(\d+)[.)]\s+(.+)$/);
    if (item) {
      flushParagraph();
      if (!list) { list = node('ol', 'statement-list'); container.append(list); }
      const li = node('li');
      li.value = Number(item[1]);
      renderMathInto(li, item[2]);
      list.append(li);
    } else {
      list = null;
      paragraph.push(line);
    }
  }
  flushParagraph();
}

function appendCriteriaText(description, value) {
  const line = value.trim();
  if (!line) return;
  const roman = line.match(/^(IV|III|II|I|V)\)\s*(.*)$/);
  if (roman) {
    const item = node('p', 'criteria-element');
    item.append(node('strong', '', `${roman[1]})`), document.createTextNode(' '));
    renderMathInto(item, roman[2]);
    description.append(item);
    return;
  }
  const alternative = line.match(/^(И\s*\(ИЛИ\)|ИЛИ)\s*(.*)$/);
  if (alternative) {
    const item = node('p', 'criteria-alternative');
    item.append(node('strong', '', alternative[1]), document.createTextNode(' '));
    renderMathInto(item, alternative[2]);
    description.append(item);
    return;
  }
  const paragraph = node('p');
  renderMathInto(paragraph, line);
  description.append(paragraph);
}

function renderCriteria(container, text) {
  const scoreLine = /^\\\((\d+)\\\)\s+балл[аов]*[.:]\s*(.*)$/;
  const scoreWord = value => value === 1 ? 'балл' : value >= 2 && value <= 4 ? 'балла' : 'баллов';
  let description = null;
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) continue;
    if (line.startsWith('Кратк')) {
      description = null;
      const note = node('p', 'criteria-note');
      renderMathInto(note, line);
      container.append(note);
      continue;
    }
    if (line.startsWith('Критерий')) {
      description = null;
      const heading = node('h5', 'criteria-heading');
      renderMathInto(heading, line);
      container.append(heading);
      continue;
    }
    const score = line.match(scoreLine);
    if (score) {
      const points = Number(score[1]);
      if (/^Максимальный балл\.?$/.test(score[2].trim())) {
        description = null;
        container.append(node('p', 'criteria-maximum', `Максимум: ${points} ${scoreWord(points)}`));
        continue;
      }
      const item = node('div', 'criteria-item');
      item.append(node('span', 'criteria-points', `${points} ${scoreWord(points)}`));
      description = node('div', 'criteria-description');
      appendCriteriaText(description, score[2]);
      item.append(description);
      container.append(item);
      continue;
    }
    if (line.startsWith('Максимум')) description = null;
    if (description) {
      appendCriteriaText(description, line);
      continue;
    }
    const paragraph = node('p', 'criteria-maximum');
    renderMathInto(paragraph, line);
    container.append(paragraph);
  }
}

function addDisclosure(card, label, content, figures = null, problem = null) {
  const button = node('button', 'detail-button', label);
  button.type = 'button';
  button.setAttribute('aria-expanded', 'false');
  const panel = node('div', 'detail-panel');
  panel.hidden = true;
  const header = node('div', 'detail-panel-header');
  const copySubject = ({ Ответ: 'ответа', Решение: 'решения', Критерии: 'критериев' })[label];
  const actions = node('div', 'detail-panel-actions');
  actions.append(copyButton(`Скопировать текст ${copySubject}`, content?.includes('[[formula:') ? 'Копировать текст' : 'Копировать TeX', content || 'В источнике не указан.'));
  const editableField = { Ответ: 'answer', Решение: 'solution' }[label];
  if (state.editingEnabled && editableField && problem) {
    actions.prepend(editLatexButton(problem, editableField));
  }
  header.append(node('h4', '', label), actions);
  const body = node('div', label === 'Критерии' ? 'detail-content criteria-content' : 'detail-content');
  if (label === 'Критерии') renderCriteria(body, content || 'В источнике не указан.');
  else renderStatement(body, content || 'В источнике не указан.');
  panel.append(header, body);
  if (figures) panel.append(figures);
  button.addEventListener('click', () => {
    panel.hidden = !panel.hidden;
    button.setAttribute('aria-expanded', String(!panel.hidden));
  });
  card.querySelector('.problem-footer').append(button);
  card.append(panel);
}

function openImage(asset, caption = 'Рисунок к заданию') {
  const dialog = byId('image-dialog');
  dialog.querySelector('img').src = asset.url;
  dialog.querySelector('p').textContent = caption;
  const download = dialog.querySelector('.image-dialog-download');
  download.href = asset.url;
  download.download = asset.url.split('/').at(-1).split('?')[0];
  dialog.showModal();
}

function figureDownload(asset, problem, role, index) {
  const link = node('a', 'figure-download');
  link.href = asset.url;
  const extension = asset.url.split('.').at(-1).split('?')[0];
  link.download = `${problem.exam_year}-${problem.variant_number}-${problem.problem_number}-${role}-${index + 1}.${extension}`;
  link.title = `Скачать рисунок ${index + 1}`;
  link.setAttribute('aria-label', link.title);
  const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  icon.setAttribute('viewBox', '0 0 24 24');
  icon.setAttribute('aria-hidden', 'true');
  for (const pathData of ['M12 3v12m0 0 4-4m-4 4-4-4', 'M4 17v3h16v-3']) {
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', pathData);
    icon.append(path);
  }
  link.append(icon);
  return link;
}

function renderFigureGrid(problem, role, selectedIndices = null) {
  const figures = problem.assets?.filter(a => a.role === role && a.media_type.startsWith('image/')) || [];
  if (!figures.length) return null;
  const figureGrid = node('div', 'task-figures');
  if (selectedIndices) figureGrid.classList.add('matching-figures');
  const numberedGraphGallery = role === 'statement_figure' && !selectedIndices
    && figures.length === 5 && matchingLayout(problem)?.gallery;
  if (numberedGraphGallery) figureGrid.classList.add('numbered-graph-gallery');
  const allFiguresSelected = !selectedIndices || selectedIndices.length === figures.length;
  const figureRowCount = role === 'statement_figure' && allFiguresSelected
    ? window.PhysEgeConditionFigureRows?.[`${problem.exam_year}-${problem.variant_number}-${problem.problem_number}`]
    : null;
  const isConditionRow = figureRowCount === figures.length;
  if (isConditionRow) figureGrid.classList.add('condition-figure-row', `condition-figure-row-${figureRowCount}`);
  const numberedPhotos = role === 'statement_figure' && figures.length === 3
    && /рис\.\s*\\\(1\\\)/i.test(problem.statement || '');
  const figureCaptions = role === 'statement_figure' ? matchingLayout(problem)?.figureCaptions : null;
  for (const [index, asset] of figures.entries()) {
    if (selectedIndices && !selectedIndices.includes(index)) continue;
    const imageName = role === 'solution_figure'
      ? `Рисунок ${index + 1} к решению задания ${problem.problem_number}`
      : `Рисунок ${index + 1} к заданию ${problem.problem_number}`;
    const item = node('figure', 'task-figure-item');
    const figure = node('button', 'task-figure');
    figure.type = 'button';
    figure.title = 'Увеличить рисунок';
    const img = node('img');
    img.src = asset.url;
    img.loading = 'lazy';
    img.alt = imageName;
    figure.append(img);
    figure.addEventListener('click', () => openImage(asset, imageName));
    item.append(figure);
    if (numberedGraphGallery) item.append(node('span', 'graph-choice-number', `${index + 1})`));
    item.append(figureDownload(asset, problem, role, index));
    if (numberedPhotos || figureCaptions?.[index]) {
      const caption = node('figcaption', 'task-figure-caption');
      caption.append(node('span', 'task-figure-number', figureCaptions?.[index] || `Рис. ${index + 1}`));
      item.append(caption);
    }
    figureGrid.append(item);
  }
  return figureGrid;
}

function matchingLayout(problem) {
  return window.PhysEgeMatchingLayouts?.[
    `${problem.exam_year}-${problem.variant_number}-${problem.problem_number}`];
}

function renderStatementWithFigures(container, problem, text, gallery = false) {
  const figures = renderFigureGrid(problem, 'statement_figure');
  const singleFigure = figures?.children.length === 1;
  const body = singleFigure ? node('div', 'statement-body') : container;
  renderStatement(body, text, problem.response_labels);
  if (gallery && figures?.children.length === 5) {
    const graphNumberHeader = [...body.querySelectorAll('.latex-table')].find(table =>
      table.rows.length === 1 && table.rows[0].cells.length === 5);
    graphNumberHeader?.closest('.latex-table-wrap')?.remove();
  }
  if (singleFigure) {
    container.classList.add('single-figure-layout');
    container.append(body);
  }
  if (figures) container.append(figures);
}

function matchingInstructionBeforeChoices(value) {
  const instruction = value.match(/К каждой позиции первого столбца[^\n.!?]*\./i);
  if (!instruction) return value;
  const rest = (value.slice(0, instruction.index) + value.slice(instruction.index + instruction[0].length))
    .replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
  const lines = rest.split('\n');
  const firstChoice = lines.findIndex(line => /^[ \t]*(?:[АA][.)][ \t]+|1[.)][ \t]+|\\begin\{tabular\}|[А-ЯЁ][А-ЯЁ \t]{4,}:?[ \t]*$)/.test(line));
  if (firstChoice < 0) return `${rest}\n\n${instruction[0]}`;
  return [lines.slice(0, firstChoice).join('\n').trim(), instruction[0],
    lines.slice(firstChoice).join('\n').trim()].filter(Boolean).join('\n\n');
}

function renderMatchingStatement(container, problem) {
  let text = matchingInstructionBeforeChoices(problem.statement || 'Условие не извлечено.');
  const layout = matchingLayout(problem);
  const allFigures = problem.assets?.filter(a => a.role === 'statement_figure' && a.media_type.startsWith('image/')) || [];
  if (!layout || layout.gallery) {
    renderStatementWithFigures(container, problem, text, Boolean(layout?.gallery));
    return;
  }
  // Some DOCX imports keep the borderless matching columns as a TeX tabular.
  // Flatten only this specific A/Б table into the same source lines as newer tasks.
  text = text.replace(/\\begin\{tabular\}\{[^}]*\}([\s\S]*?)\\end\{tabular\}/g, (whole, body) => {
    const rows = latexTableRows(body);
    if (!rows.some(row => /^[АA][.)]/.test(row))) return whole;
    return rows.map(row => {
      const cells = row.split(/(?<!\\)&/).map(cell => cell.trim()).filter(Boolean);
      return cells.join('\n');
    }).join('\n');
  });
  const lines = text.split('\n');
  const firstOption = lines.findIndex(line => /^\s*1[.)]\s+/.test(line));
  const firstLetter = lines.findIndex(line => /^\s*[АA][.)]\s+/.test(line));
  if (firstOption < 0 || (!layout.graphFigures && !layout.responseLabels && firstLetter < 0)) {
    renderStatementWithFigures(container, problem, text);
    return;
  }
  const firstColumnLine = firstLetter >= 0 && firstLetter < firstOption ? firstLetter : firstOption;
  const headingRx = /^\s*(?:ГРАФИКИ|ПРОЦЕССЫ?|ФИЗИЧЕСКИЕ ВЕЛИЧИНЫ|ФИЗИЧЕСКАЯ ВЕЛИЧИНА|ФОРМУЛЫ?|ЭНЕРГИЯ ФОТОНА|ЭНЕРГЕТИЧЕСКИЕ ПЕРЕХОДЫ|ХАРАКТЕРИСТИКИ ПРОЦЕССОВ|НОМЕРА ПРОЦЕССОВ|ДВИЖЕНИЕ ЧАСТИЦЫ|ТРАЕКТОРИЯ|УЧАСТКИ ГРАФИКА)(?:\s*[АA]\s*и\s*[БB])?\s*:?(?:\s*)$/i;
  const normalizeHeading = value => value.trim().replace(/:\s*$/, '').replace(/\s+/g, ' ').toUpperCase();
  const isHeading = line => headingRx.test(line) || layout.headings?.some(
    heading => normalizeHeading(line) === normalizeHeading(heading));
  let prefixEnd = firstColumnLine;
  while (prefixEnd > 0 && (!lines[prefixEnd - 1].trim() || isHeading(lines[prefixEnd - 1]))) prefixEnd--;
  renderStatement(container, lines.slice(0, prefixEnd).join('\n').trim(), problem.response_labels);

  const left = [], right = [];
  if (layout.responseLabels && firstLetter < 0) {
    for (const [index, label] of (answerTableLabels(problem) || []).entries()) {
      left.push(`${'АБВ'[index] || index + 1}) ${label}`);
    }
  }
  let destination = firstLetter >= 0 && firstLetter < firstOption ? left : right;
  let leftTitle = layout.headings?.[0] || (layout.graphFigures ? 'ГРАФИКИ' : '');
  let rightTitle = layout.headings?.[1] || (layout.graphFigures ? 'ФИЗИЧЕСКИЕ ВЕЛИЧИНЫ' : '');
  for (const raw of lines.slice(prefixEnd)) {
    const line = raw.trim();
    if (!line) continue;
    if (isHeading(line)) {
      if (layout.headings) continue;
      if (/ГРАФИКИ|ПРОЦЕСС|ФИЗИЧЕСКИЕ ВЕЛИЧИНЫ/i.test(line) && !leftTitle) leftTitle = line.replace(/:$/, '');
      else if (/ФИЗИЧЕСКИЕ ВЕЛИЧИНЫ|ФОРМУЛЫ|ЭНЕРГИЯ ФОТОНА/i.test(line)) rightTitle = line.replace(/:$/, '');
      continue;
    }
    if (/^1[.)]\s+/.test(line)) destination = right;
    if (/^[АAБB][.)]\s+/.test(line)) {
      destination = left;
      if (layout.graphFigures && /^[АAБB][.)]\s*график\s*[АAБB]\s*$/i.test(line)) continue;
    }
    destination.push(line);
  }
  if (!right.length || (!left.length && !layout.graphFigures)) {
    container.replaceChildren();
    renderStatementWithFigures(container, problem, text);
    return;
  }
  const graphCount = Math.min(layout.graphFigures || 0, allFigures.length);
  const firstGraph = allFigures.length - graphCount;
  const preceding = renderFigureGrid(problem, 'statement_figure',
    Array.from({ length: firstGraph }, (_, index) => index));
  if (preceding && firstGraph === 1) {
    const intro = node('div', 'single-figure-layout');
    const body = node('div', 'statement-body');
    body.append(...container.children);
    intro.append(body, preceding);
    container.append(intro);
  } else if (preceding && firstGraph) {
    container.append(preceding);
  }
  const table = node('div', 'matching-columns');
  const leftColumn = node('div', 'matching-column');
  const rightColumn = node('div', 'matching-column');
  if (leftTitle) leftColumn.append(node('div', 'matching-heading', leftTitle));
  if (rightTitle) rightColumn.append(node('div', 'matching-heading', rightTitle));
  for (const item of left) {
    const row = node('div', 'matching-left-item');
    renderMathInto(row, item);
    leftColumn.append(row);
  }
  if (graphCount) {
    const graphGrid = renderFigureGrid(problem, 'statement_figure',
      Array.from({ length: graphCount }, (_, index) => firstGraph + index));
    if (graphCount === 2) {
      for (const [index, item] of [...graphGrid.children].entries()) {
        item.classList.add('matching-labeled-graph');
        item.prepend(node('span', 'matching-graph-label', `${'АБ'[index]})`));
      }
    }
    leftColumn.append(graphGrid);
  }
  renderProse(rightColumn, right.join('\n'));
  table.append(leftColumn, rightColumn);
  container.append(table);
}

function renderCard(problem, showSource, numberMode = false) {
  const card = node('article', 'problem-card panel');
  const shownNumber = numberMode ? problem.target_problem_number : problem.problem_number;
  card.id = `task-${shownNumber}-${problem.id}`;
  const header = node('div', 'problem-card-header');
  const heading = node('div', 'problem-heading');
  heading.append(node('span', 'problem-number', String(shownNumber)));
  const title = problem.alternative_number > 1 ? `Альтернативный пример ${problem.alternative_number}` : 'Задание';
  heading.append(node('h3', '', title));
  heading.append(node('span', 'problem-meta', `${topicLabel(problem.topic)} · ${problem.max_points} ${problem.max_points === 1 ? 'балл' : 'балла'}`));
  if (!numberMode && [2022, 2023].includes(problem.exam_year) && ['yes', 'partial'].includes(problem.verdict)) {
    heading.append(node('span', 'problem-target', `№${problem.target_problem_number} в 2027`));
  }
  header.append(heading);
  const statusClass = ['yes', 'no', 'partial'].includes(problem.verdict) ? problem.verdict : 'unassessed';
  const status = node('span', `problem-state ${statusClass}`, labelForStatus(problem.verdict));
  status.title = problem.relevance_reason || '';
  header.append(status);
  card.append(header);

  const statementToolbar = node('div', 'statement-toolbar');
  const copyStatement = statementForCopy(problem);
  if (state.editingEnabled) statementToolbar.append(editLatexButton(problem, 'statement'));
  statementToolbar.append(copyButton('Скопировать текст условия', copyStatement.includes('[[formula:') ? 'Копировать текст' : 'Копировать TeX', copyStatement));
  card.append(statementToolbar);

  const statement = node('div', 'statement');
  renderMatchingStatement(statement, problem);
  card.append(statement);
  const responseTable = renderResponseTable(problem, true);
  if (responseTable) card.append(responseTable);
  const answerField = renderAnswerField(problem, true);
  if (answerField) card.append(answerField);

  const footer = node('div', 'problem-footer');
  card.append(footer);
  addDisclosure(card, 'Ответ', problem.answer, null, problem);
  if (problem.solution) addDisclosure(card, 'Решение', problem.solution,
    renderFigureGrid(problem, 'solution_figure'), problem);
  if (problem.criteria) addDisclosure(card, 'Критерии', problem.criteria);

  if (showSource) {
    const source = node('div', 'review-note');
    source.append(document.createTextNode('Источник: '));
    const link = node('a', 'source-link', variantDisplayTitle(problem));
    link.href = `/?view=variants&variant=${encodeURIComponent(problem.variant_id)}`;
    source.append(link);
    if (numberMode && shownNumber !== problem.problem_number) {
      source.append(document.createTextNode(` · исходное задание №${problem.problem_number}`));
    }
    card.append(source);
  }
  return card;
}

function readLocation() {
  const url = new URL(location.href);
  state.view = ['numbers', 'builder', 'automatic'].includes(url.searchParams.get('view')) ? url.searchParams.get('view') : 'variants';
  state.variantId = url.searchParams.get('variant') || state.variantId || state.variants[0]?.id || null;
  state.automaticId = url.searchParams.get('auto') || state.automaticId || state.automaticVariants[0]?.id || null;
  const n = Number(url.searchParams.get('number'));
  state.number = Number.isInteger(n) && n >= 1 && n <= 26 ? n : 1;
}

function writeLocation() {
  const url = new URL(location.href);
  url.searchParams.set('view', state.view);
  if (state.view === 'automatic') {
    if (state.automaticId) url.searchParams.set('auto', state.automaticId);
    url.searchParams.delete('variant');
    url.searchParams.delete('number');
  } else if (state.view !== 'numbers') {
    url.searchParams.set('variant', state.variantId);
    url.searchParams.delete('auto');
    url.searchParams.delete('number');
  } else {
    url.searchParams.set('number', String(state.number));
    url.searchParams.delete('variant');
    url.searchParams.delete('auto');
  }
  history.pushState({}, '', url);
}

function renderSidebar() {
  byId('tab-variants').classList.toggle('is-active', state.view === 'variants');
  byId('tab-automatic').classList.toggle('is-active', state.view === 'automatic');
  byId('tab-numbers').classList.toggle('is-active', state.view === 'numbers');
  byId('tab-builder').classList.toggle('is-active', state.view === 'builder');
  byId('tab-variants').setAttribute('aria-current', state.view === 'variants' ? 'page' : 'false');
  byId('tab-automatic').setAttribute('aria-current', state.view === 'automatic' ? 'page' : 'false');
  byId('tab-numbers').setAttribute('aria-current', state.view === 'numbers' ? 'page' : 'false');
  byId('tab-builder').setAttribute('aria-current', state.view === 'builder' ? 'page' : 'false');
  byId('sidebar-eyebrow').textContent = state.view === 'variants' ? 'Варианты' : state.view === 'automatic' ? 'Автоварианты' : state.view === 'numbers' ? 'Позиции ЕГЭ' : 'Сборка';
  byId('sidebar-title').textContent = ['variants', 'automatic'].includes(state.view) ? 'Выберите вариант' : state.view === 'numbers' ? 'Выберите номер' : 'Выберите задачи';
  byId('variant-list').hidden = state.view !== 'variants';
  byId('automatic-list').hidden = state.view !== 'automatic';
  byId('number-list').hidden = state.view !== 'numbers';
  byId('builder-sidebar').hidden = state.view !== 'builder';
  const variants = byId('variant-list');
  const variantScrollTop = variants.scrollTop;
  const expandedYears = new Set([...variants.querySelectorAll('.variant-year[open]')].map(group => group.dataset.year));
  const selectedVariant = state.variants.find(variant => variant.id === state.variantId);
  if (!variants.children.length || variants.dataset.selectedId !== state.variantId) {
    expandedYears.clear();
    if (selectedVariant) expandedYears.add(String(selectedVariant.exam_year));
  }
  variants.replaceChildren();
  variants.dataset.selectedId = state.variantId || '';
  const byYear = new Map();
  for (const variant of state.variants) {
    if (!byYear.has(variant.exam_year)) byYear.set(variant.exam_year, []);
    byYear.get(variant.exam_year).push(variant);
  }
  for (const [year, yearVariants] of byYear) {
    const group = node('details', 'variant-year');
    group.dataset.year = String(year);
    group.open = expandedYears.has(String(year));
    const heading = node('summary', 'variant-year-heading', String(year));
    heading.setAttribute('aria-label', `Варианты ${year} года`);
    heading.addEventListener('click', () => {
      if (!group.open) {
        for (const other of variants.querySelectorAll('.variant-year')) {
          if (other !== group) other.open = false;
        }
      }
    });
    const options = node('div', 'variant-year-options');
    for (const variant of yearVariants) {
      const button = node('button', `variant-option ${variant.id === state.variantId ? 'is-active' : ''}`);
      button.type = 'button';
      if (variant.id === state.variantId) button.setAttribute('aria-current', 'true');
      button.append(node('strong', '', variantDisplayTitle(variant)));
      button.addEventListener('click', () => { state.variantId = variant.id; writeLocation(); update(); });
      options.append(button);
    }
    group.append(heading, options);
    variants.append(group);
  }
  variants.scrollTop = variantScrollTop;
  const automatics = byId('automatic-list');
  const automaticScrollTop = automatics.scrollTop;
  automatics.replaceChildren();
  for (const item of state.automaticVariants) {
    const button = node('button', `variant-option ${item.id === state.automaticId ? 'is-active' : ''}`);
    button.type = 'button';
    if (item.id === state.automaticId) button.setAttribute('aria-current', 'true');
    button.append(node('strong', '', item.title), node('small', '', `Основа: ${automaticBaseTitle(item)}`));
    button.addEventListener('click', () => { state.automaticId = item.id; writeLocation(); update(); });
    automatics.append(button);
  }
  automatics.scrollTop = automaticScrollTop;
  const numbers = byId('number-list');
  numbers.replaceChildren();
  for (let n = 1; n <= 26; n++) {
    const button = node('button', `number-option ${n === state.number ? 'is-active' : ''}`, String(n));
    button.type = 'button';
    button.setAttribute('aria-label', `Задание ${n}`);
    button.addEventListener('click', () => { state.number = n; writeLocation(); update(); });
    numbers.append(button);
  }
}

function generatedLink(label, href, newTab = false) {
  const link = node('a', 'source-download', label);
  link.href = href;
  if (newTab) { link.target = '_blank'; link.rel = 'noopener'; }
  return link;
}

function renderBuilder() {
  const list = byId('builder-list');
  list.replaceChildren();
  if (!state.options.length) {
    list.append(node('p', 'panel problem-card', 'Загрузка списка задач…'));
    fetch('/api/variant-options').then(response => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    }).then(options => { state.options = options; if (state.view === 'builder') renderBuilder(); })
      .catch(error => { list.replaceChildren(node('p', 'error-box', `Не удалось загрузить выбор задач: ${error.message}`)); });
    return;
  }
  const base = state.options.filter(item => item.variant_id === state.variantId && item.alternative_number === 1);
  for (let number = 1; number <= 26; number++) {
    const candidates = state.options.filter(item => item.problem_number === number);
    if (!state.picks[number]) state.picks[number] = base.find(item => item.problem_number === number)?.id || candidates[0]?.id;
    const row = node('div', 'builder-row panel');
    row.append(node('strong', '', `Задание ${number}`));
    const controls = node('div', 'builder-controls');
    const select = node('select', 'builder-select');
    select.setAttribute('aria-label', `Задание ${number}: исходный вариант`);
    for (const option of candidates) {
      const sourceNumber = option.source_problem_number !== number ? ` · исходное №${option.source_problem_number}` : '';
      const entry = node('option', '', `${variantDisplayTitle(option)}${sourceNumber}${option.alternative_number > 1 ? ` · пример ${option.alternative_number}` : ''}`);
      entry.value = option.id;
      select.append(entry);
    }
    select.value = state.picks[number];
    const status = node('span', 'problem-state');
    function updateStatus() {
      const selected = candidates.find(item => item.id === select.value);
      const verdict = selected?.verdict;
      status.className = `problem-state ${['yes', 'no', 'partial'].includes(verdict) ? verdict : 'unassessed'}`;
      status.textContent = labelForStatus(verdict);
      status.title = selected?.relevance_reason || '';
    }
    updateStatus();
    const preview = node('div', 'builder-preview statement');
    preview.hidden = true;
    const show = node('button', 'builder-preview-button', 'Показать условие');
    show.type = 'button';
    const actions = node('div', 'builder-actions');
    actions.append(show, status);
    async function loadPreview() {
      preview.replaceChildren(node('p', '', 'Загрузка…'));
      try {
        const response = await fetch(`/api/problems/${encodeURIComponent(select.value)}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const problem = await response.json();
        preview.replaceChildren();
        renderMatchingStatement(preview, problem);
        const responseTable = renderResponseTable(problem);
        if (responseTable) preview.append(responseTable);
        const answerField = renderAnswerField(problem);
        if (answerField) preview.append(answerField);
      } catch (error) { preview.replaceChildren(node('p', '', `Не удалось загрузить условие: ${error.message}`)); }
    }
    select.addEventListener('change', () => { state.picks[number] = select.value; updateStatus(); renderBuilderLinks(); if (!preview.hidden) loadPreview(); });
    show.addEventListener('click', () => {
      preview.hidden = !preview.hidden;
      show.textContent = preview.hidden ? 'Показать условие' : 'Скрыть условие';
      if (!preview.hidden) loadPreview();
    });
    controls.append(select, actions, preview);
    row.append(controls);
    list.append(row);
  }
  renderBuilderLinks();
}

function renderBuilderLinks() {
  const links = byId('generated-downloads');
  links.replaceChildren();
  if (state.view === 'numbers' || (state.view === 'automatic' && !state.automaticId)) return;
  const ids = state.view === 'builder'
    ? encodeURIComponent(Array.from({ length: 26 }, (_, i) => state.picks[i + 1]).join(',')) : '';
  const href = (document, format) => state.view === 'builder'
    ? `/api/assemble?ids=${ids}&document=${document}&format=${format}`
    : state.view === 'automatic'
      ? `/api/automatic-variants/${encodeURIComponent(state.automaticId)}/${document === 'conditions' ? '' : document + '/'}${format}`
      : `/api/variants/${encodeURIComponent(state.variantId)}/${document === 'conditions' ? '' : document + '/'}${format}`;
  for (const [document, title] of [
    ['conditions', 'Условия'], ['answers', 'Ответы'],
    ['solutions', 'Решения'], ['criteria', 'Критерии']
  ]) {
    const group = node('div', 'generated-download-group');
    group.append(node('span', 'generated-download-label', title));
    for (const format of ['pdf', 'tex']) {
      group.append(format === 'pdf'
        ? generatedLink('Смотреть PDF', href(document, 'pdf'), true)
        : generatedLink('Скачать TeX', href(document, 'tex')));
    }
    if (document === 'conditions' || document === 'solutions') {
      group.append(generatedLink('TeX с рисунками (.zip)', href(document, 'zip')));
    }
    links.append(group);
  }
}

async function update() {
  renderSidebar();
  const variant = state.variants.find(v => v.id === state.variantId);
  const automatic = state.automaticVariants.find(v => v.id === state.automaticId);
  byId('content-eyebrow').textContent = state.view === 'variants' ? 'Цельный вариант' : state.view === 'automatic' ? 'Автоматически собранный вариант' : state.view === 'numbers' ? 'Все варианты' : 'Новый вариант';
  byId('content-title').textContent = state.view === 'variants' ? (variant ? variantDisplayTitle(variant) : 'Вариант не найден') : state.view === 'automatic' ? (automatic?.title || 'Собранных вариантов пока нет') : state.view === 'numbers' ? `Задание №${state.number}` : 'Собрать из выбранных задач';
  const baseLink = byId('base-variant');
  baseLink.hidden = state.view !== 'automatic' || !automatic;
  if (!baseLink.hidden) {
    baseLink.textContent = `Основа: ${automaticBaseTitle(automatic)}`;
    baseLink.href = `/?view=variants&variant=${encodeURIComponent(automatic.base_variant_id)}`;
  }
  const sourceDownload = byId('source-download');
  const sourceDownloads = byId('source-downloads');
  sourceDownloads.hidden = state.view !== 'variants' || !variant?.download_url;
  if (!sourceDownloads.hidden) {
    sourceDownload.href = variant.download_url;
    sourceDownload.textContent = 'Скачать исходник';
  }
  const list = byId('problem-list');
  list.replaceChildren();
  byId('correspondence').replaceChildren();
  byId('correspondence').hidden = true;
  list.hidden = state.view === 'builder';
  byId('builder-list').hidden = state.view !== 'builder';
  if (state.view === 'builder') {
    byId('problem-count').textContent = '26 заданий';
    byId('problem-count').className = 'count-pill';
    byId('error-box').hidden = true;
    renderBuilder();
    return;
  }
  renderBuilderLinks();
  const countPill = byId('problem-count');
  if ((state.view === 'variants' && variant) || (state.view === 'automatic' && automatic)) {
    const selected = state.view === 'automatic' ? automatic : variant;
    const suitable = selected.suitable_count;
    const total = state.view === 'automatic' ? 26 : selected.position_count;
    const complete = total === 26 && suitable === 26;
    const partial = selected.partially_suitable_count || 0;
    countPill.textContent = complete ? 'Подходит для 2027 года' : total === 30
      ? `Для 2027: ${suitable} полностью, ${partial} частично из 30`
      : `Подходит ${suitable} задач из 26`;
    countPill.className = `count-pill ${complete ? 'is-suitable' : 'is-partial'}`;
  } else {
    countPill.textContent = 'Загрузка…';
    countPill.className = 'count-pill';
  }
  byId('error-box').hidden = true;
  if (state.view === 'automatic' && !automatic) {
    list.append(node('div', 'panel problem-card', 'Собранных вариантов пока нет.'));
    countPill.textContent = '';
    return;
  }
  try {
    const url = state.view === 'automatic'
      ? `/api/automatic-variants/${encodeURIComponent(state.automaticId)}/problems`
      : `/api/problems?${state.view === 'variants' ? `variant_id=${encodeURIComponent(state.variantId)}` : `number=${state.number}`}`;
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Ошибка HTTP ${response.status}`);
    const problems = await response.json();
    renderCorrespondence(problems, variant);
    if (state.view === 'numbers') countPill.textContent = plural(problems.length, 'задача', 'задачи', 'задач');
    if (!problems.length) list.append(node('div', 'panel problem-card', 'Задачи пока не загружены.'));
    else for (const problem of problems) list.append(renderCard(problem,
      ['numbers', 'automatic'].includes(state.view), state.view === 'numbers'));
  } catch (error) {
    if (state.view === 'numbers') countPill.textContent = '';
    byId('error-box').textContent = `Не удалось загрузить задачи: ${error.message}`;
    byId('error-box').hidden = false;
  }
}

async function init() {
  try {
    const [variantsResponse, automaticResponse, configResponse] = await Promise.all([
      fetch('/api/variants'), fetch('/api/automatic-variants'), fetch('/api/config')
    ]);
    if (!variantsResponse.ok || !automaticResponse.ok || !configResponse.ok) throw new Error('Не удалось загрузить варианты');
    state.variants = await variantsResponse.json();
    state.automaticVariants = await automaticResponse.json();
    state.editingEnabled = Boolean((await configResponse.json()).editing_enabled);
    const total = state.variants.reduce((sum, item) => sum + item.problem_count, 0);
    byId('database-summary').textContent = `${plural(state.variants.length, 'вариант', 'варианта', 'вариантов')} · ${plural(total, 'запись', 'записи', 'записей')} задач`;
    readLocation();
    await update();
  } catch (error) {
    byId('content-title').textContent = 'База недоступна';
    byId('error-box').textContent = error.message;
    byId('error-box').hidden = false;
  }
}

byId('tab-variants').addEventListener('click', () => { state.view = 'variants'; writeLocation(); update(); });
byId('tab-automatic').addEventListener('click', () => { state.view = 'automatic'; writeLocation(); update(); });
byId('tab-numbers').addEventListener('click', () => { state.view = 'numbers'; writeLocation(); update(); });
byId('tab-builder').addEventListener('click', () => { state.view = 'builder'; writeLocation(); update(); });
window.addEventListener('popstate', () => { readLocation(); update(); });
byId('image-dialog').addEventListener('click', event => { if (event.target === event.currentTarget) event.currentTarget.close(); });
byId('latex-editor-close').addEventListener('click', () => byId('latex-editor').close());
byId('latex-editor-cancel').addEventListener('click', () => byId('latex-editor').close());
byId('latex-editor-save').addEventListener('click', saveLatexEdit);
byId('latex-editor-text').addEventListener('input', renderLatexEditorPreview);
byId('latex-editor-text').addEventListener('keydown', event => {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
    event.preventDefault();
    saveLatexEdit();
  }
});
init();
