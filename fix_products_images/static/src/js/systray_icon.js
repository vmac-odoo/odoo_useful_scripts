/** @odoo-module **/
import { registry } from "@web/core/registry"
import { useService } from "@web/core/utils/hooks"
import { Component, xml } from "@odoo/owl"
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";

class FixProductImagesIcon extends Component {
  static template = xml`
        <templates xml:space="preserve">
            <t t-name="systray_icon" owl="1">
                <Dropdown>
                    <button><i class="fa fa-lg fa-wrench" aria-hidden="true"></i></button>
                    <t t-set-slot="content">
                        <DropdownItem onSelected.bind="() => this._fix_product_template()">Click to Fix Product Template Images</DropdownItem>
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
  }
  async generate_report() {
    const [result_id] = await this.orm.create("ir.logging", [
      {
        type: "client",
        name: "Fix Image REPORT",
        path: "fix_products/static/src/js/systray_icon.js",
        line: "16",
        func: "generate_report",
        message: this.report.join("\n"),
      },
    ])
    this.action.doAction({
      type: "ir.actions.act_window",
      name: "Logging",
      res_model: "ir.logging",
      res_id: result_id,
      view_mode: "form",
      views: [[false, "form"]],
      target: "new",
    })
  }

  reporter(log) {
    console.log(log)
    this.report.push(log)
  }

  async create_missing(records) {
    this.reporter("****** BEGINING FIXER SCRIPT ******")
    const total = records.length
    let current = 0
    for (const record of records) {
      current++;
      const percentage = (current / total) * 100
      this.reporter(`Processing: ${percentage.toFixed(2)}% completed`)
      const { id, name, image_1920 } = record
      this.reporter("################################")
      this.reporter(`FIXING PRODUCT [${name}] (${id})`)
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
        this.reporter(`CREATED IMAGE SIZE ${size} WITH id(s) ${resizedId}`)
        referenceId = referenceId || resizedId // Keep track of original.
        // Converted to JPEG for use in PDF files, alpha values will default to white
        const final_jpeg = await this.orm.call(
          "ir.attachment",
          "create_unique",
          [
            [
              {
                name: name.replace(/\.webp$/, ".jpg"),
                description: "format: jpeg",
                datas: canvas.toDataURL("image/jpeg", 0.75).split(",")[1],
                res_id: resizedId,
                res_model: "ir.attachment",
                mimetype: "image/jpeg",
              },
            ],
          ]
        )
        this.reporter(
          `CREATED IMAGE JPEG WITH SIZE ${size} WITH id(s) ${final_jpeg}`
        )
      }
      // End Part of Odoo. See LICENSE file for full copyright and licensing details.
      this.reporter("################################")
    }
  }

  async _fix_product_template() {
    const products = await this.orm.searchRead(
        "product.template",
        [],
        ["id", "name", "image_1920"]
      )
      this.reporter(`FOUND ${products.length} PRODUCTS!`)
      const products_with_image = products.filter((r) => r["image_1920"])
      this.reporter(`FOUND ${products_with_image.length} PRODUCTS WITH IMAGES!`)
      await this.create_missing(products_with_image)
      this.reporter("****** ENDED FIXER SCRIPT ******")
      this.generate_report()
  }
}

FixProductImagesIcon.components = { Dropdown, DropdownItem }
export const systrayItem = { Component: FixProductImagesIcon }
registry
  .category("systray")
  .add("FixProductImagesIcon", systrayItem, { sequence: 1 })
