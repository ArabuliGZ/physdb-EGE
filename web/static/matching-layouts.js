/* Reusable borderless two-column matching layout. Keys are source year-variant-task.
 * Add future matching tasks here; the renderer extracts А/Б and 1–4 from statement TeX.
 * graphFigures is the number of trailing statement images that belong in the left column.
 * headings fixes the printed titles above the left and right matching columns.
 */
window.PhysEgeMatchingLayouts = Object.freeze({
  '2027-ДЕМО-15': { graphFigures: 1 }, '2027-ДЕМО-17': {},
  '2026-4-6': { graphFigures: 2 },
  '2026-4-17': { headings: ['ПРОЦЕСС', 'ЭНЕРГИЯ ФОТОНА'] },
  '2025-1-1-17': { headings: ['ПРОЦЕСС', 'ЭНЕРГИЯ ФОТОНА'] }, '2025-1-2-15': { graphFigures: 2 },
  '2025-2-1-17': { headings: ['ПРОЦЕСС', 'ЭНЕРГИЯ ФОТОНА'] }, '2025-2-2-15': { graphFigures: 2 },
  '2024-1-1-6': { graphFigures: 2 },
  '2024-1-3-10': {}, '2024-1-3-15': { graphFigures: 2 },
  '2024-1-3-17': { headings: ['ПРОЦЕСС', 'ЭНЕРГЕТИЧЕСКИЕ ПЕРЕХОДЫ'] },
  '2024-1-4-6': { graphFigures: 2 }, '2024-1-4-10': {},
  '2024-2-2-6': { graphFigures: 2 }, '2024-2-3-6': { graphFigures: 2 },
  '2024-2-4-6': { graphFigures: 2 },
  '2023-1-6': { graphFigures: 2 },
  '2023-1-11': { headings: ['ФИЗИЧЕСКИЕ ВЕЛИЧИНЫ', 'ФОРМУЛЫ'] },
  '2023-1-17': { headings: ['ФИЗИЧЕСКИЕ ВЕЛИЧИНЫ', 'ФОРМУЛЫ'] },
  '2023-1-19': { headings: ['ПРОЦЕССЫ', 'ЭНЕРГЕТИЧЕСКИЕ ПЕРЕХОДЫ'] },
  '2023-2-6': { graphFigures: 2 },
  '2023-2-11': { headings: ['ПРОЦЕССЫ', 'ФИЗИЧЕСКИЕ ВЕЛИЧИНЫ'] },
  '2023-2-17': { headings: ['ФИЗИЧЕСКИЕ ВЕЛИЧИНЫ', 'ФОРМУЛЫ'] },
  // 2023-2-19 has only the printed answer table, with no matching-choice columns.
  '2023-3-6': {},
  '2023-3-11': { headings: ['ХАРАКТЕРИСТИКИ ПРОЦЕССОВ', 'НОМЕРА ПРОЦЕССОВ'] },
  '2023-3-17': { headings: ['ФОРМУЛЫ', 'ФИЗИЧЕСКИЕ ВЕЛИЧИНЫ'] },
  '2023-3-19': { graphFigures: 1 },
  '2022-1-8': { headings: ['ФОРМУЛЫ', 'ФИЗИЧЕСКИЕ ВЕЛИЧИНЫ'] },
  '2022-1-19': { headings: ['ДВИЖЕНИЕ ЧАСТИЦЫ', 'ТРАЕКТОРИЯ'],
    answerLabels: ['А', 'Б'], figureCaptions: ['Рис. 1', 'Рис. 2'] },
  '2022-2-8': { headings: ['ФИЗИЧЕСКАЯ ВЕЛИЧИНА', 'ФОРМУЛА'] },
  '2022-2-19': {},
  '2022-2-21': { headings: ['ПРОЦЕССЫ', 'ЭНЕРГЕТИЧЕСКИЕ ПЕРЕХОДЫ'] },
  '2022-3-8': { headings: ['ФИЗИЧЕСКИЕ ВЕЛИЧИНЫ', 'ФОРМУЛЫ'] },
  '2022-3-13': { headings: ['УЧАСТКИ ГРАФИКА', 'ПРОЦЕССЫ'] },
  '2022-3-19': { graphFigures: 2 },
  '2022-4-8': { graphFigures: 2 }, '2022-4-19': {},
  // Numbered graph galleries: the figures are 1–5, not А/Б.
  '2023-1-21': { gallery: true }, '2023-2-21': { gallery: true }, '2023-3-21': { gallery: true },
  '2022-1-2': { gallery: true }, '2022-2-2': { gallery: true },
  '2022-3-2': { gallery: true }, '2022-3-23': { gallery: true },
  '2022-4-2': { gallery: true },
  // Five printed picture choices cropped from one source-page image.
  '2027-ДЕМО-20': { gallery: true }, '2026-1-20': { gallery: true },
  '2025-1-2-20': { gallery: true }, '2025-2-2-20': { gallery: true },
  '2024-1-4-20': { gallery: true }, '2024-2-2-20': { gallery: true },
});

// Only illustrations belonging to the question itself. Graphs offered as answer
// choices are deliberately excluded, even when stored as statement_figure assets.
window.PhysEgeConditionFigureRows = Object.freeze({
  '2025-1-2-14': 2, '2025-1-2-21': 2,
  '2025-2-2-14': 2, '2025-2-2-21': 2,
  '2024-1-2-21': 2, '2024-2-3-21': 2,
  '2023-1-24': 2, '2023-3-24': 2,
  '2022-1-19': 2, '2022-3-17': 2,
  '2022-2-24': 3,
});
