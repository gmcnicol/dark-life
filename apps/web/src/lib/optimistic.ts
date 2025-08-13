export async function optimisticUpdate<T>(
  current: T,
  apply: (v: T) => void,
  next: T,
  action: () => Promise<unknown>,
): Promise<void> {
  const prev = current;
  apply(next);
  try {
    await action();
  } catch (err) {
    apply(prev);
    throw err;
  }
}
