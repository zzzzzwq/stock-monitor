const api = require('../../utils/api')
const app = getApp()

Page({
  data: {
    holdings: [],
    showForm: false,
    editing: false,
    editId: null,
    markets: ['深圳 sz', '上海 sh'],
    form: {
      code: '',
      name: '',
      marketIndex: 0,
      shares: '',
      cost_per_share: ''
    }
  },

  onShow() {
    if (!app.isLoggedIn()) {
      wx.reLaunch({ url: '/pages/login/login' })
      return
    }
    this.loadHoldings()
  },

  async loadHoldings() {
    try {
      const res = await api.getHoldings()
      this.setData({ holdings: res })
    } catch (err) {
      wx.showToast({ title: '加载失败', icon: 'none' })
    }
  },

  showAddForm() {
    this.setData({
      showForm: true,
      editing: false,
      editId: null,
      form: { code: '', name: '', marketIndex: 0, shares: '', cost_per_share: '' }
    })
  },

  cancelForm() {
    this.setData({ showForm: false, editing: false })
  },

  onFieldChange(e) {
    const field = e.currentTarget.dataset.field
    const value = e.detail.value
    this.setData({ [`form.${field}`]: value })
  },

  onMarketChange(e) {
    this.setData({ 'form.marketIndex': e.detail.value })
  },

  async saveHolding() {
    const f = this.data.form
    if (!f.code || !f.name || !f.shares || !f.cost_per_share) {
      wx.showToast({ title: '请填写完整信息', icon: 'none' })
      return
    }

    const market = this.data.markets[f.marketIndex].match(/[a-z]+$/)[0]
    const data = {
      code: f.code,
      name: f.name,
      market,
      shares: parseInt(f.shares),
      cost_per_share: parseFloat(f.cost_per_share)
    }

    try {
      if (this.data.editing && this.data.editId) {
        await api.updateHolding(this.data.editId, data)
        wx.showToast({ title: '修改成功' })
      } else {
        await api.addHolding(data)
        wx.showToast({ title: '添加成功' })
      }
      this.setData({ showForm: false, editing: false })
      this.loadHoldings()
    } catch (err) {
      wx.showToast({ title: '操作失败', icon: 'none' })
    }
  },

  editHolding(e) {
    const id = e.currentTarget.dataset.id
    const h = this.data.holdings.find(x => x.id === id)
    if (!h) return

    const marketIndex = this.data.markets.findIndex(m => m.includes(h.market))
    this.setData({
      showForm: true,
      editing: true,
      editId: id,
      form: {
        code: h.code,
        name: h.name,
        marketIndex: marketIndex >= 0 ? marketIndex : 0,
        shares: h.shares.toString(),
        cost_per_share: h.cost_per_share.toString()
      }
    })
  },

  deleteHolding(e) {
    const id = e.currentTarget.dataset.id
    wx.showModal({
      title: '确认删除',
      content: '确定删除该持仓？',
      success: async (res) => {
        if (res.confirm) {
          await api.deleteHolding(id)
          wx.showToast({ title: '删除成功' })
          this.loadHoldings()
        }
      }
    })
  }
})
