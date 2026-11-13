const state = { view: 'variants', variantId: null, automaticId: null, number: 1,
  variants: [], automaticVariants: [], options: [], picks: {} };
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

function renderCorrespondence(problems, variant) {
  const host = byId('correspondence');
  host.replaceChildren();
  host.hidden = true;
  if (state.view !== 'variants' || variant?.exam_year !== 2023 || !problems.length) return;

  const panel = node('section', 'correspondence-panel panel');
  panel.append(node('h3', '', 'Соответствие номеров: 2023 → 2027'));
  panel.append(node('p', 'correspondence-intro',
    'Позиция 2027 определяется по теме, формату ответа и баллам. Для неподходящих задач показан ближайший проверенный кандидат; в каталог 2027 они не включены.'));
  const scroll = node('div', 'correspondence-scroll');
  const table = node('table', 'correspondence-table');
  const head = node('thead');
  const headings = node('tr');
  for (const label of ['№ 2023', '№ 2027 / кандидат', 'Оценка', 'Основание']) {
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
  return variant.is_official_demo ? variant.title :
    `Демидова ${variant.exam_year}-${variant.variant_number}`;
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
  dialog.showModal();
}

function renderFigureGrid(problem, role, showCopyButton = true) {
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
    item.append(figure);
    if (showCopyButton) {
      const caption = node('figcaption', 'task-figure-caption');
      caption.append(copyButton(`Скопировать ${imageName.toLowerCase()}`, 'Копировать рисунок', asset, 'image'));
      item.append(caption);
    }
    figureGrid.append(item);
  }
  return figureGrid;
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
  if (!numberMode && problem.exam_year === 2023 && ['yes', 'partial'].includes(problem.verdict)) {
    heading.append(node('span', 'problem-target', `№${problem.target_problem_number} в 2027`));
  }
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
      const entry = node('option', '', `${option.is_official_demo ? option.variant_title : `Демидова ${option.exam_year}-${option.variant_number}`}${sourceNumber}${option.alternative_number > 1 ? ` · пример ${option.alternative_number}` : ''}`);
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
        renderStatement(preview, problem.statement || 'Условие не извлечено.');
        const figures = renderFigureGrid(problem, 'statement_figure', false);
        if (figures) preview.append(figures);
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
    const [variantsResponse, automaticResponse] = await Promise.all([
      fetch('/api/variants'), fetch('/api/automatic-variants')
    ]);
    if (!variantsResponse.ok || !automaticResponse.ok) throw new Error('Не удалось загрузить варианты');
    state.variants = await variantsResponse.json();
    state.automaticVariants = await automaticResponse.json();
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
init();
