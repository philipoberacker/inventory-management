<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div class="card">
      <div class="card-header">
        <h3 class="card-title">{{ t('restocking.budget') }}</h3>
      </div>
      <div class="budget-panel">
        <div class="budget-readout">{{ currencySymbol }}{{ budget.toLocaleString() }}</div>
        <input
          type="range"
          v-model.number="budget"
          min="0"
          max="5000"
          step="100"
          class="budget-slider"
        />
        <p class="budget-hint">{{ t('restocking.budgetHint') }}</p>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <h3 class="card-title">
          {{ t('restocking.recommendations') }}
          <span class="badge info rec-count-badge">
            {{ recommendation.line_items.length }} {{ t('restocking.itemsRecommended') }}
          </span>
        </h3>
      </div>
      <p class="rec-hint">{{ t('restocking.recommendationsHint') }}</p>

      <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
      <div v-else-if="recommendation.line_items.length === 0" class="empty-state">
        {{ t('restocking.noItemsFit') }}
      </div>
      <div v-else>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.itemName') }}</th>
                <th>{{ t('restocking.table.quantity') }}</th>
                <th>{{ t('restocking.table.unitCost') }}</th>
                <th>{{ t('restocking.table.lineTotal') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="li in recommendation.line_items" :key="li.sku">
                <td><strong>{{ li.sku }}</strong></td>
                <td>{{ li.name }}</td>
                <td>{{ li.quantity }}</td>
                <td>{{ currencySymbol }}{{ li.unit_price.toLocaleString() }}</td>
                <td><strong>{{ currencySymbol }}{{ li.line_total.toLocaleString() }}</strong></td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="summary-row">
          <div class="summary-item">
            <span class="summary-label">{{ t('restocking.totalCost') }}</span>
            <span class="summary-value">{{ currencySymbol }}{{ recommendation.total_cost.toLocaleString() }}</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">{{ t('restocking.remainingBudget') }}</span>
            <span class="summary-value">{{ currencySymbol }}{{ recommendation.remaining_budget.toLocaleString() }}</span>
          </div>
          <div class="summary-lead-time">
            {{ t('restocking.leadTimeDays', { days: 14 }) }}
          </div>
        </div>
      </div>

      <div v-if="error" class="error">{{ error }}</div>

      <div v-if="successOrder" class="success-banner">
        <p>{{ t('restocking.orderPlaced', { orderNumber: successOrder.order_number, date: formatDate(successOrder.expected_delivery) }) }}</p>
        <p class="view-in-orders">{{ t('restocking.viewInOrders') }}</p>
      </div>

      <div class="place-order-row">
        <button
          class="btn-primary"
          :disabled="placing || recommendation.line_items.length === 0"
          @click="placeOrder"
        >
          {{ placing ? t('restocking.placing') : t('restocking.placeOrder') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, currentLocale } = useI18n()

    const currencySymbol = computed(() => {
      return currentCurrency.value === 'JPY' ? '¥' : '$'
    })

    const budget = ref(2500)
    const recommendation = ref({ line_items: [], total_cost: 0, remaining_budget: 0 })
    const loading = ref(false)
    const placing = ref(false)
    const error = ref(null)
    const successOrder = ref(null)

    let debounceTimer = null

    const loadRecommendation = async () => {
      loading.value = true
      error.value = null
      try {
        recommendation.value = await api.getRestockRecommendation(budget.value)
      } catch (err) {
        error.value = 'Failed to load recommendation: ' + err.message
        console.error(err)
      } finally {
        loading.value = false
      }
    }

    watch(budget, () => {
      successOrder.value = null
      if (debounceTimer) clearTimeout(debounceTimer)
      debounceTimer = setTimeout(() => {
        loadRecommendation()
      }, 300)
    })

    const placeOrder = async () => {
      placing.value = true
      error.value = null
      try {
        successOrder.value = await api.placeRestockOrder(budget.value)
        await loadRecommendation()
      } catch (err) {
        error.value = 'Failed to place order: ' + err.message
        console.error(err)
      } finally {
        placing.value = false
      }
    }

    const formatDate = (dateString) => {
      const date = new Date(dateString)
      if (isNaN(date.getTime())) return dateString
      const locale = currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'
      return date.toLocaleDateString(locale, {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      })
    }

    onMounted(loadRecommendation)

    return {
      t,
      currencySymbol,
      budget,
      recommendation,
      loading,
      placing,
      error,
      successOrder,
      placeOrder,
      formatDate
    }
  }
}
</script>

<style scoped>
.budget-panel {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.5rem 0;
}

.budget-readout {
  font-size: 2.5rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

.budget-slider {
  width: 100%;
  accent-color: #2563eb;
  height: 6px;
  cursor: pointer;
}

.budget-hint {
  font-size: 0.813rem;
  color: #64748b;
  margin: 0;
}

.rec-count-badge {
  margin-left: 0.75rem;
  font-size: 0.75rem;
  vertical-align: middle;
}

.rec-hint {
  font-size: 0.875rem;
  color: #64748b;
  margin-bottom: 1rem;
}

.empty-state {
  text-align: center;
  padding: 2rem;
  color: #64748b;
  font-size: 0.938rem;
}

.summary-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 1.5rem;
  padding: 1rem 0.75rem;
  border-top: 2px solid #e2e8f0;
  margin-top: 0.5rem;
  background: #f8fafc;
  border-radius: 0 0 8px 8px;
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.summary-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.summary-value {
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
}

.summary-lead-time {
  margin-left: auto;
  font-size: 0.813rem;
  color: #64748b;
  font-style: italic;
}

.place-order-row {
  margin-top: 1.25rem;
  display: flex;
  justify-content: flex-end;
}

.btn-primary {
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 8px;
  padding: 0.625rem 1.5rem;
  font-size: 0.938rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease;
}

.btn-primary:hover:not(:disabled) {
  background: #1d4ed8;
}

.btn-primary:disabled {
  background: #94a3b8;
  cursor: not-allowed;
}

.success-banner {
  background: #d1fae5;
  color: #065f46;
  border: 1px solid #6ee7b7;
  border-radius: 8px;
  padding: 1rem 1.25rem;
  margin-top: 1rem;
  font-size: 0.938rem;
  font-weight: 500;
}

.success-banner p {
  margin: 0;
}

.success-banner .view-in-orders {
  margin-top: 0.375rem;
  font-size: 0.875rem;
  color: #047857;
}
</style>
