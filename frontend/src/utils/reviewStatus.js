export const REVIEW_STATUS = Object.freeze({
  NUEVA: 'nueva',
  EN_REVISION: 'en_revision',
  ATENDIDA: 'atendida',
})

export const REVIEW_STATUS_OPTIONS = Object.freeze([
  { value: REVIEW_STATUS.NUEVA, label: 'Nueva' },
  { value: REVIEW_STATUS.EN_REVISION, label: 'En revisión' },
  { value: REVIEW_STATUS.ATENDIDA, label: 'Atendida' },
])
