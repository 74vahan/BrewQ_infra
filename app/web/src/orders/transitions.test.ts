import { describe, expect, it } from 'vitest';
import { actionsFor } from './transitions.ts';

describe('actionsFor: buttons come only from allowed_transitions', () => {
  it('NEW offers start and cancel', () => {
    expect(actionsFor({ status: 'NEW', allowed_transitions: ['IN_PROGRESS', 'CANCELLED'] })).toEqual({
      forward: ['IN_PROGRESS'],
      canCancel: true,
    });
  });

  it('IN_PROGRESS offers ready and cancel', () => {
    expect(actionsFor({ status: 'IN_PROGRESS', allowed_transitions: ['READY', 'CANCELLED'] })).toEqual({
      forward: ['READY'],
      canCancel: true,
    });
  });

  it('READY offers only picked up, no cancel', () => {
    expect(actionsFor({ status: 'READY', allowed_transitions: ['PICKED_UP'] })).toEqual({
      forward: ['PICKED_UP'],
      canCancel: false,
    });
  });

  it('final statuses have no buttons', () => {
    expect(actionsFor({ status: 'PICKED_UP', allowed_transitions: [] })).toEqual({ forward: [], canCancel: false });
    expect(actionsFor({ status: 'CANCELLED', allowed_transitions: [] })).toEqual({ forward: [], canCancel: false });
  });

  it('does not invent a button the server did not offer', () => {
    expect(actionsFor({ status: 'NEW', allowed_transitions: ['CANCELLED'] })).toEqual({
      forward: [],
      canCancel: true,
    });
    expect(actionsFor({ status: 'NEW', allowed_transitions: [] })).toEqual({ forward: [], canCancel: false });
  });

  it('never draws a backward move, even if the server offers one', () => {
    const ready = { status: 'READY', allowed_transitions: ['IN_PROGRESS', 'PICKED_UP'] } as never;
    expect(actionsFor(ready).forward).toEqual(['PICKED_UP']);
    const inProgress = { status: 'IN_PROGRESS', allowed_transitions: ['NEW', 'READY'] } as never;
    expect(actionsFor(inProgress).forward).toEqual(['READY']);
  });

  it('ignores statuses from the future that have no label', () => {
    const order = { status: 'NEW', allowed_transitions: ['IN_PROGRESS', 'ARCHIVED'] } as never;
    expect(actionsFor(order)).toEqual({ forward: ['IN_PROGRESS'], canCancel: false });
  });
});
