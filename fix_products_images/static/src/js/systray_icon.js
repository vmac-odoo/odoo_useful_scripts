/** @odoo-module **/
import { registry } from "@web/core/registry"
import { useService } from "@web/core/utils/hooks"
import { Component, xml } from "@odoo/owl"
import { Dropdown } from "@web/core/dropdown/dropdown"
import { DropdownItem } from "@web/core/dropdown/dropdown_item"

const SCRIPT_PATH = "fix_products/static/src/js/systray_icon.js"

class FixProductImagesIcon extends Component {
  static template = xml`
    <templates xml:space="preserve">
      <t t-name="systray_icon" owl="1">
        <Dropdown>
          <button>
            <i class="fa fa-lg fa-wrench" aria-hidden="true"></i>
          </button>
          <t t-set-slot="content">
            <DropdownItem onSelected.bind="() => this.fixProductImages()">Click to Fix Product Template Images</DropdownItem>
          </t>
        </Dropdown>
      </t>
    </templates>
  `

  setup() {
    super.setup(...arguments)
    this.orm = useService("orm")
    this.action = useService("action")
    this.report = []
    this.jpegQueue = []
  }

  log(message) {
    console.log(message)
    this.report.push(message)
  }

  logSection(title = "", marker = "=") {
    const line = marker.repeat(50)
    this.log(`\n${line}\n${title}\n${line}\n`)
  }

  async flushJPEGQueue() {
    if (!this.jpegQueue.length) {
      this.logSection("NO JPEG IMAGES TO PROCESS", "*")
      return
    }

    this.logSection("PROCESSING JPEG QUEUE", "=")
    const created = await this.orm.call("ir.attachment", "create_unique", [
      this.jpegQueue,
    ])
    this.log(`Created ${created.length} JPEG images with id(s): ${created.toString()}.`)
    this.jpegQueue = []
  }

  async generateReport() {
    this.logSection("GENERATING FINAL REPORT", "*")
    const [logId] = await this.orm.create("ir.logging", [
      {
        type: "client",
        name: "Fix Image Report",
        path: SCRIPT_PATH,
        line: "16",
        func: "generateReport",
        message: this.report.join("\n"),
      },
    ])

    this.action.doAction({
      type: "ir.actions.act_window",
      name: "Logging",
      res_model: "ir.logging",
      res_id: logId,
      view_mode: "form",
      views: [[false, "form"]],
      target: "new",
    })
  }

  async createMissingImages(products) {
    this.logSection("STARTING IMAGE FIX SCRIPT")

    const total = products.length
    let count = 0

    for (const product of products) {
      count++
      const { id, name, image_1920 } = product
      const progress = ((count / total) * 100).toFixed(2)
      this.logSection(`PROGRESS COMPLETED: ${progress}% Complete`, '#')
      this.logSection(
        `Processing [${name}] (${id})`,
        "-"
      )

      // Begin Part of Odoo. See LICENSE file for full copyright and licensing details.
      // Generate alternate sizes and format for reports.
      const image = document.createElement("img")
      image.src = `data:image/webp;base64,${image_1920}`
      await new Promise((resolve) => image.addEventListener("load", resolve))
      const originalSize = Math.max(image.width, image.height)
      const smallerSizes = [1024, 512, 256, 128].filter(
        (size) => size < originalSize
      )
      let referenceId = undefined

      for (const size of [originalSize, ...smallerSizes]) {
        const ratio = size / originalSize
        const canvas = document.createElement("canvas")
        canvas.width = image.width * ratio
        canvas.height = image.height * ratio
        const ctx = canvas.getContext("2d")
        ctx.fillStyle = "transparent"
        ctx.fillRect(0, 0, canvas.width, canvas.height)
        ctx.imageSmoothingEnabled = true
        ctx.imageSmoothingQuality = "high"
        ctx.drawImage(
          image,
          0,
          0,
          image.width,
          image.height,
          0,
          0,
          canvas.width,
          canvas.height
        )
        const [resizedId] = await this.orm.call(
          "ir.attachment",
          "create_unique",
          [
            [
              {
                name: name,
                description: size === originalSize ? "" : `resize: ${size}`,
                datas:
                  size === originalSize
                    ? image_1920
                    : canvas.toDataURL("image/webp", 0.75).split(",")[1],
                res_id: referenceId,
                res_model: "ir.attachment",
                mimetype: "image/webp",
              },
            ],
          ]
        )
        this.log(`Created WebP image (${size}px), ID: ${resizedId}`)
        referenceId = referenceId || resizedId // Keep track of original.
        // Converted to JPEG for use in PDF files, alpha values will default to white
        this.log(`Queued JPEG (${size}px) for [${name}]`)
        this.jpegQueue.push(
          {
            name: name.replace(/\.webp$/, ".jpg"),
            description: "format: jpeg",
            datas: canvas.toDataURL("image/jpeg", 0.75).split(",")[1],
            res_id: resizedId,
            res_model: "ir.attachment",
            mimetype: "image/jpeg",
          }
        )
      }
      await this.flushJPEGQueue()
      // End Part of Odoo. See LICENSE file for full copyright and licensing details.
      
    }
    
    this.logSection("ALL PRODUCTS PROCESSED", "*")
  }

  async fixProductImages() {
    performance.mark("fix_start")

    const products = await this.orm.searchRead("product.template", [], ["id", "name", "image_1920"])
    this.log(`Found ${products.length} products.`)

    const productsWithImages = products.filter((p) => p.image_1920)
    this.log(`Found ${productsWithImages.length} products with images.`)

    await this.createMissingImages(productsWithImages)

    performance.mark("fix_end")
    const duration = performance.measure(
      "fix_perf",
      "fix_start",
      "fix_end"
    ).duration
    this.log(`Image fix completed in ${(duration / 1000).toFixed(2)} min.`)
    await this.generateReport()
  }
}

FixProductImagesIcon.components = { Dropdown, DropdownItem }

export const systrayItem = { Component: FixProductImagesIcon }

registry
  .category("systray")
  .add("FixProductImagesIcon", systrayItem, { sequence: 1 })
