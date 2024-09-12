import { useSelector } from "react-redux"

import { describe, it, beforeEach } from "@jest/globals"
import { render, screen } from "@testing-library/react"

import { FlexItemList } from "components/Workspace/Visualize/FlexItemList"

// Mock the VisualizeItemAddButton only
jest.mock("components/Workspace/Visualize/VisualizeItemAddButton", () => ({
  VisualizeItemAddButton: jest.fn(({ itemId }) => (
    <button data-testid={`add-button-${itemId || "new"}`}>Add Button</button>
  )),
}))

// Mock useSelector
jest.mock("react-redux", () => ({
  useSelector: jest.fn(),
}))

describe("FlexItemList Component", () => {
  beforeEach(() => {
    jest.clearAllMocks() // Clear previous mocks before each test
  })

  it("renders VisualizeItem components based on the layout from the Redux store", () => {
    // Arrange
    const mockLayout = [[1, 2], [3]]

    // Mock the return value of useSelector to return the layout
    ;(useSelector as jest.Mock).mockReturnValue(mockLayout)

    // Act
    render(<FlexItemList />)

    // Assert - Check if the correct VisualizeItem components are rendered
    mockLayout.forEach((row) => {
      row.forEach((itemId) => {
        expect(screen.getByText(`VisualizeItem ${itemId}`)).toBeInTheDocument()
      })
      // Ensure AddButton for the last item in each row is rendered
      expect(
        screen.getByTestId(`add-button-${row[row.length - 1]}`),
      ).toBeInTheDocument()
    })

    // Check if the final AddButton is rendered without itemId
    expect(screen.getByTestId("add-button-new")).toBeInTheDocument()
  })

  it("renders empty layout without VisualizeItem when layout is empty", () => {
    // Arrange - Mock an empty layout
    ;(useSelector as jest.Mock).mockReturnValue([])

    // Act
    render(<FlexItemList />)

    // Assert - Check no VisualizeItem is rendered
    expect(screen.queryByText(/VisualizeItem/)).toBeNull()

    // Check if the final AddButton is rendered
    expect(screen.getByTestId("add-button-new")).toBeInTheDocument()
  })
})
