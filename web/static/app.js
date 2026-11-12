const state = { view: 'variants', variantId: null, number: 1, variants: [] };
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

function labelForStatus(verdict) {
  return verdict === 'yes' ? 'Подходит для 2027' :
         verdict === 'no' ? 'Не подходит для 2027' :
         verdict === 'partial' ? 'Частично подходит' : 'Не оценено';
}

function topicLabel(topic) {
  return ({ mechanics: 'Механика', molecular: 'Молекулярная физика',
    electrodynamics: 'Электродинамика', quantum: 'Квантовая физика',
    cross_topic: 'Общие вопросы и эксперимент' })[topic] || topic;
}

function variantDisplayTitle(variant) {
  return variant.is_official_demo ? variant.title :
    `Демидова ${variant.exam_year}-${variant.variant_number}`;
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
    if (window.katex) {
      window.katex.render(match[1] ?? match[2], math, { throwOnError: false, output: 'htmlAndMathml', displayMode: display });
    } else {
      math.textContent = match[1] ?? match[2];
    }
    container.append(math);
    cursor = match.index + match[0].length;
  }
  if (cursor < value.length) container.append(document.createTextNode(value.slice(cursor)));
}

function renderStatement(container, text) {
  const rx = /\\begin\{tabular\}\{[^}]*\}([\s\S]*?)\\end\{tabular\}/g;
  let cursor = 0;
  for (const match of text.matchAll(rx)) {
    if (match.index > cursor) {
      renderProse(container, text.slice(cursor, match.index));
    }
    const wrap = node('div', 'latex-table-wrap');
    const table = node('table', 'latex-table');
    const rows = match[1].split(/\\\\\s*\n/).filter(row => row.trim());
    if (rows.length === 1 && rows[0].split(/(?<!\\)&/).length === 2) {
      table.classList.add('answer-grid');
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

function addDisclosure(card, label, content, figures = null) {
  const button = node('button', 'detail-button', label);
  button.type = 'button';
  button.setAttribute('aria-expanded', 'false');
  const panel = node('div', 'detail-panel');
  panel.hidden = true;
  const header = node('div', 'detail-panel-header');
  const copySubject = ({ Ответ: 'ответа', Решение: 'решения', Критерии: 'критериев' })[label];
  header.append(
    node('h4', '', label),
    copyButton(`Скопировать текст ${copySubject}`, content?.includes('[[formula:') ? 'Копировать текст' : 'Копировать TeX', content || 'В источнике не указан.')
  );
  const body = node('div', 'detail-content');
  renderStatement(body, content || 'В источнике не указан.');
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
  dialog.showModal();
}

function renderFigureGrid(problem, role) {
  const figures = problem.assets?.filter(a => a.role === role && a.media_type.startsWith('image/')) || [];
  if (!figures.length) return null;
  const figureGrid = node('div', 'task-figures');
  for (const [index, asset] of figures.entries()) {
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
    const caption = node('figcaption', 'task-figure-caption');
    caption.append(copyButton(`Скопировать ${imageName.toLowerCase()}`, 'Копировать рисунок', asset, 'image'));
    item.append(figure, caption);
    figureGrid.append(item);
  }
  return figureGrid;
}

function renderCard(problem, showSource) {
  const card = node('article', 'problem-card panel');
  card.id = `task-${problem.problem_number}-${problem.alternative_number}`;
  const header = node('div', 'problem-card-header');
  const heading = node('div', 'problem-heading');
  heading.append(node('span', 'problem-number', String(problem.problem_number)));
  const title = problem.alternative_number > 1 ? `Альтернативный пример ${problem.alternative_number}` : 'Задание';
  heading.append(node('h3', '', title));
  heading.append(node('span', 'problem-meta', `${topicLabel(problem.topic)} · ${problem.max_points} ${problem.max_points === 1 ? 'балл' : 'балла'}`));
  header.append(heading);
  const statusClass = ['yes', 'no', 'partial'].includes(problem.verdict) ? problem.verdict : 'unassessed';
  const status = node('span', `problem-state ${statusClass}`, labelForStatus(problem.verdict));
  status.title = problem.relevance_reason || '';
  header.append(status);
  card.append(header);

  const statementToolbar = node('div', 'statement-toolbar');
  statementToolbar.append(copyButton('Скопировать текст условия', problem.statement?.includes('[[formula:') ? 'Копировать текст' : 'Копировать TeX', problem.statement || 'Условие не извлечено.'));
  card.append(statementToolbar);

  const statement = node('div', 'statement');
  renderStatement(statement, problem.statement || 'Условие не извлечено.');
  card.append(statement);

  const figures = renderFigureGrid(problem, 'statement_figure');
  if (figures) card.append(figures);

  const footer = node('div', 'problem-footer');
  card.append(footer);
  addDisclosure(card, 'Ответ', problem.answer);
  if (problem.solution) addDisclosure(card, 'Решение', problem.solution,
    renderFigureGrid(problem, 'solution_figure'));
  if (problem.criteria) addDisclosure(card, 'Критерии', problem.criteria);

  if (showSource) {
    const source = node('div', 'review-note');
    source.append(document.createTextNode('Источник: '));
    const link = node('a', 'source-link', problem.variant_title);
    link.href = `/?view=variants&variant=${encodeURIComponent(problem.variant_id)}`;
    source.append(link);
    card.append(source);
  }
  return card;
}

function readLocation() {
  const url = new URL(location.href);
  state.view = url.searchParams.get('view') === 'numbers' ? 'numbers' : 'variants';
  state.variantId = url.searchParams.get('variant') || state.variants[0]?.id || null;
  const n = Number(url.searchParams.get('number'));
  state.number = Number.isInteger(n) && n >= 1 && n <= 26 ? n : 1;
}

function writeLocation() {
  const url = new URL(location.href);
  url.searchParams.set('view', state.view);
  if (state.view === 'variants') {
    url.searchParams.set('variant', state.variantId);
    url.searchParams.delete('number');
  } else {
    url.searchParams.set('number', String(state.number));
    url.searchParams.delete('variant');
  }
  history.pushState({}, '', url);
}

function renderSidebar() {
  byId('tab-variants').classList.toggle('is-active', state.view === 'variants');
  byId('tab-numbers').classList.toggle('is-active', state.view === 'numbers');
  byId('tab-variants').setAttribute('aria-current', state.view === 'variants' ? 'page' : 'false');
  byId('tab-numbers').setAttribute('aria-current', state.view === 'numbers' ? 'page' : 'false');
  byId('sidebar-eyebrow').textContent = state.view === 'variants' ? 'Варианты' : 'Позиции ЕГЭ';
  byId('sidebar-title').textContent = state.view === 'variants' ? 'Выберите вариант' : 'Выберите номер';
  byId('variant-list').hidden = state.view !== 'variants';
  byId('number-list').hidden = state.view !== 'numbers';
  const variants = byId('variant-list');
  const variantScrollTop = variants.scrollTop;
  variants.replaceChildren();
  for (const variant of state.variants) {
    const button = node('button', `variant-option ${variant.id === state.variantId ? 'is-active' : ''}`);
    button.type = 'button';
    button.append(node('strong', '', variantDisplayTitle(variant)));
    button.addEventListener('click', () => { state.variantId = variant.id; writeLocation(); update(); });
    variants.append(button);
  }
  variants.scrollTop = variantScrollTop;
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

async function update() {
  renderSidebar();
  const variant = state.variants.find(v => v.id === state.variantId);
  byId('content-eyebrow').textContent = state.view === 'variants' ? 'Цельный вариант' : 'Все варианты';
  byId('content-title').textContent = state.view === 'variants' ? (variant ? variantDisplayTitle(variant) : 'Вариант не найден') : `Задание №${state.number}`;
  const sourceDownload = byId('source-download');
  sourceDownload.hidden = state.view !== 'variants' || !variant?.download_url;
  if (!sourceDownload.hidden) sourceDownload.href = variant.download_url;
  const companions = byId('companion-downloads');
  companions.replaceChildren();
  if (state.view === 'variants' && variant?.companions) {
    const names = { answer_key: 'Ключ ответов', criteria: 'Критерии', pdf_copy: 'PDF-копия' };
    for (const item of variant.companions) {
      const link = node('a', 'source-download', names[item.role] || item.role);
      link.href = item.download_url;
      companions.append(link);
    }
  }
  const list = byId('problem-list');
  list.replaceChildren();
  byId('problem-count').textContent = 'Загрузка…';
  byId('error-box').hidden = true;
  try {
    const query = state.view === 'variants' ? `variant_id=${encodeURIComponent(state.variantId)}` : `number=${state.number}`;
    const response = await fetch(`/api/problems?${query}`);
    if (!response.ok) throw new Error(`Ошибка HTTP ${response.status}`);
    const problems = await response.json();
    byId('problem-count').textContent = plural(problems.length, 'задача', 'задачи', 'задач');
    if (!problems.length) list.append(node('div', 'panel problem-card', 'Задачи пока не загружены.'));
    else for (const problem of problems) list.append(renderCard(problem, state.view === 'numbers'));
  } catch (error) {
    byId('problem-count').textContent = '';
    byId('error-box').textContent = `Не удалось загрузить задачи: ${error.message}`;
    byId('error-box').hidden = false;
  }
}

async function init() {
  try {
    const response = await fetch('/api/variants');
    if (!response.ok) throw new Error(`Ошибка HTTP ${response.status}`);
    state.variants = await response.json();
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
byId('tab-numbers').addEventListener('click', () => { state.view = 'numbers'; writeLocation(); update(); });
window.addEventListener('popstate', () => { readLocation(); update(); });
byId('image-dialog').addEventListener('click', event => { if (event.target === event.currentTarget) event.currentTarget.close(); });
init();
