import apiClient from './apiClient.js'


export async function importReviews(file) {
  const formData = new FormData()
  formData.append('file', file)

  const { data } = await apiClient.post('/reviews/import', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })

  return data
}
