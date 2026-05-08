const api = require('../../utils/api')
const app = getApp()

Page({
  data: {
    loading: true,
    isTradingDay: false,
    indices: [],
    holdings: [],
    totalPnl: 0,
    techData: {},
    techKeys: []
  },

  onShow() {
    if (!app.isLoggedIn()) {
      wx.reLaunch({ url: '/pages/login/login' })
      return
    }
    this.loadData()
  },

  async loadData() {
    this.setData({ loading: true })
    try {
      const res = await api.getSummary()
      const indicesList = []
      for (const [name, data] of Object.entries(res.indices || {})) {
        indicesList.push({ name, ...data })
      }

      const techMap = {}
      const techKeys = []
      for (const [code, data] of Object.entries(res.tech_data || {})) {
        const h = (res.holdings || []).find(x => x.code === code)
        techMap[code] = { ...data, name: h ? h.name : code }
        techKeys.push(code)
      }

      this.setData({
        loading: false,
        isTradingDay: res.is_trading_day,
        indices: indicesList,
        holdings: res.holdings || [],
        totalPnl: res.total_pnl || 0,
        techData: techMap,
        techKeys
      })
    } catch (err) {
      this.setData({ loading: false })
      wx.showToast({ title: '加载失败', icon: 'none' })
    }
  },

  goDetail(e) {
    const code = e.currentTarget.dataset.code
    wx.navigateTo({ url: `/pages/detail/detail?code=${code}` })
  },

  goAddHolding() {
    wx.switchTab({ url: '/pages/holdings/holdings' })
  },

  onPullDownRefresh() {
    this.loadData().then(() => wx.stopPullDownRefresh())
  }
})
