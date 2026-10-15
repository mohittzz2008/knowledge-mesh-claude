import type { Monaco } from '@monaco-editor/react';

export const MESH_THEME = 'mesh-dark';

export const MONACO_FONT = '"IBM Plex Mono", ui-monospace, Menlo, Consolas, monospace';

/** Dark editor theme matching the app surface tokens (#0d1014 canvas, #13171c surface, #8ab4ff accent). */
export function defineMeshTheme(monaco: Monaco) {
  monaco.editor.defineTheme(MESH_THEME, {
    base: 'vs-dark',
    inherit: true,
    rules: [
      { token: 'comment', foreground: '6b7686', fontStyle: 'italic' },
      { token: 'keyword', foreground: '8ab4ff' },
      { token: 'string', foreground: '8fd0a8' },
      { token: 'number', foreground: 'e3b04b' },
    ],
    colors: {
      'editor.background': '#0d1014',
      'editor.foreground': '#e8ecf1',
      'editorLineNumber.foreground': '#6b7686',
      'editorLineNumber.activeForeground': '#c3cbd6',
      'editor.lineHighlightBackground': '#13171c',
      'editor.selectionBackground': '#3f73e055',
      'editorCursor.foreground': '#8ab4ff',
      'editorWidget.background': '#13171c',
      'editorGutter.background': '#0d1014',
      'diffEditor.insertedTextBackground': '#5fc48d22',
      'diffEditor.removedTextBackground': '#eb6f6622',
    },
  });
}
