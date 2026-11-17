/*
 * One switch controls the math engine for the whole site.
 * Change DEFAULT_RENDERER to "katex" for an immediate server-wide rollback,
 * or add ?math=katex to the URL to compare renderers in one browser.
 */
(() => {
  'use strict';

  const DEFAULT_RENDERER = 'mathjax';
  const SUPPORTED_RENDERERS = new Set(['mathjax', 'katex']);
  const requestedRenderer = new URLSearchParams(window.location.search).get('math');
  const renderer = SUPPORTED_RENDERERS.has(requestedRenderer)
    ? requestedRenderer
    : DEFAULT_RENDERER;

  document.documentElement.dataset.mathRenderer = renderer;

  function loadStylesheet(href) {
    if (document.querySelector(`link[href="${href}"]`)) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = href;
    document.head.append(link);
  }

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = src;
      script.async = true;
      script.addEventListener('load', resolve, { once: true });
      script.addEventListener('error', () => reject(new Error(`Не удалось загрузить ${src}`)), { once: true });
      document.head.append(script);
    });
  }

  function showPlainTex(target, tex, error = null) {
    target.replaceChildren(document.createTextNode(tex));
    target.classList.toggle('math-render-error', Boolean(error));
    if (error) target.title = error.message || String(error);
  }

  // MathJax can assign 0em to inherited text while the browser paints it.
  // Reserve the actual glyph width so the following symbols cannot overlap.
  function reserveInheritedTextWidths(root) {
    for (const text of root.querySelectorAll('mjx-utext')) {
      const range = document.createRange();
      range.selectNodeContents(text);
      const paintedWidth = range.getBoundingClientRect().width;
      const reservedWidth = text.getBoundingClientRect().width;
      if (paintedWidth > reservedWidth + 0.5) {
        text.style.width = Math.ceil(paintedWidth + 1) + 'px';
      }
    }
  }

  let ready;
  let render;

  if (renderer === 'mathjax') {
    document.addEventListener('toggle', event => {
      if (event.target instanceof HTMLDetailsElement && event.target.open) {
        reserveInheritedTextWidths(event.target);
      }
    }, true);
    window.MathJax = {
      loader: {
        paths: {
          mathjax: '/static/vendor/mathjax',
          fonts: '/static/vendor',
        },
        load: ['input/tex', 'output/chtml'],
      },
      tex: {
        packages: { '[+]': ['textmacros'] },
      },
      output: {
        font: 'mathjax-stix2',
        fontPath: '[fonts]/%%FONT%%-font',
        mtextInheritFont: true,
        merrorInheritFont: true,
        displayOverflow: 'scroll',
      },
      startup: {
        typeset: false,
      },
    };

    ready = loadScript('/static/vendor/mathjax/startup.js')
      .then(() => window.MathJax.startup.promise);

    render = (target, tex, display) => {
      const renderToken = Symbol('math-render');
      target.mathRenderToken = renderToken;
      target.classList.add('is-math-pending');
      target.replaceChildren(document.createTextNode(
        display ? `\\[${tex}\\]` : `\\(${tex}\\)`,
      ));
      ready
        .then(() => {
          if (target.mathRenderToken !== renderToken || !target.isConnected) return;
          return window.MathJax.typesetPromise([target]);
        })
        .then(() => document.fonts.ready)
        .then(() => {
          if (target.mathRenderToken !== renderToken || !target.isConnected) return;
          reserveInheritedTextWidths(target);
          target.classList.remove('is-math-pending', 'math-render-error');
          target.removeAttribute('title');
        })
        .catch(error => {
          if (target.mathRenderToken !== renderToken) return;
          target.classList.remove('is-math-pending');
          showPlainTex(target, tex, error);
          console.error('MathJax rendering failed:', tex, error);
        });
    };
  } else {
    loadStylesheet('/static/katex.min.css');
    ready = loadScript('/static/katex.min.js');
    render = (target, tex, display) => {
      showPlainTex(target, tex);
      ready
        .then(() => {
          if (!target.isConnected) return;
          window.katex.render(tex, target, {
            throwOnError: false,
            output: 'htmlAndMathml',
            displayMode: display,
          });
        })
        .catch(error => showPlainTex(target, tex, error));
    };
  }

  window.PhysEgeMath = Object.freeze({
    renderer,
    ready,
    render,
  });
})();
