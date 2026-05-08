const api = require('../../utils/api')

Page({
  data: {
    code: '',
    name: '',
    loading: true,
    analysis: null
  },

  onLoad(options) {
    if (options.code) {
      this.setData({ code: options.code, name: options.name || '' })
      this.loadDetail(options.code)
    }
  },

  async loadDetail(code) {
    this.setData({ loading: true })
    try {
      const res = await api.getDetail(code)
      if (res && res.price) {
        this.setData({
          analysis: res,
          name: res.name || this.data.name,
          loading: false
        })
      } else {
        this.setData({ loading: false })
      }
    } catch (err) {
      this.setData({ loading: false })
      wx.showToast({ title: '加载失败', icon: 'none' })
    }
  }
})
