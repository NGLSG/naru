<script setup lang="ts">
import { computed } from 'vue'
import type { ArchiveEntry } from '../types'

const props = defineProps<{ entry: ArchiveEntry }>()

// Authored notation fragments for the backdrop; these are not source quotations.
const fragments: Record<string, string[]> = {
  fortran: ['      DO 10 I = 1, 10', '      S = S + I', '   10 CONTINUE'],
  algol: ['begin', '  integer i;', '  i := 1', 'end'],
  cobol: ['MOVE 1 TO COUNTER.', 'ADD 1 TO COUNTER.'],
  lisp: ["(CONS 'A '(B C))", "(CAR '(A B C))"],
  basic: ['10 LET S = 0', '20 FOR I = 1 TO 10', '30 LET S = S + I', '40 NEXT I'],
  pli: ['DECLARE I FIXED;', 'DO I = 1 TO 10;', 'END;'],
  bcpl: ['LET square(n) = n * n'],
  simula: ['begin', '  integer i;', '  i := 1;', 'end;'],
  apl: ['⍳10', '+/1 2 3'],
  pascal: ['program hello;', 'begin', "  writeln('Hello')", 'end.'],
  b: ['square(x) {', '  return(x*x);', '}'],
}
const lines = computed(() => props.entry.family === 'c'
  ? props.entry.year < 1989
    ? ['square(x)', 'int x;', '{ return x * x; }']
    : ['int square(int x)', '{', '  return x * x;', '}']
  : fragments[props.entry.family] ?? props.entry.keywords)
</script>

<template>
  <div class="language-trace" aria-hidden="true">
    <span class="trace-year">{{ entry.year }}</span>
    <div class="trace-listing"><span v-for="(line, index) in lines" :key="index"><i>{{ String(index + 1).padStart(2, '0') }}</i><code>{{ line }}</code></span></div>
    <span class="trace-register trace-register--top" /><span class="trace-register trace-register--bottom" />
  </div>
</template>
