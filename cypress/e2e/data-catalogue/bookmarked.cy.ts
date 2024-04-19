describe("Bookmarking datasets", () => {

  const assertBookmarked = ()=>{
    cy.findByRole("heading", {
      level: 3,
      name: "Source dataset",
    }).within(()=>{
      cy.findByRole("button").should("have.attr", "class", 'bookmark-toggle is-bookmarked');
      cy.findByRole("button").should("have.attr", "data-dataset-bookmarked", 'true');
      cy.findByRole("button").should("have.attr", "title", 'You have bookmarked Source dataset');
    })
  }

  const assertNotBookmarked = ()=>{
    cy.findByRole("heading", {
      level: 3,
      name: "source dataset - no permissions",
    }).within(()=>{
      cy.findByRole("button").should("have.attr", "class", 'bookmark-toggle');
      cy.findByRole("button").should("have.attr", "data-dataset-bookmarked", 'false');
      cy.findByRole("button").should("have.attr", "title", 'You have not bookmarked source dataset - no permissions');
    })
  }

  context('When directly viewing the data catalogue page', ()=>{
      beforeEach(()=>{
        cy.visit('/datasets')
      })

      it('should show a bookmarked dataset', ()=>{
        assertBookmarked()
      })

      it('should NOT show a bookmarked dataset', ()=>{
        assertNotBookmarked()
      })
  })

  context('When searching the data catalogue page', ()=>{
    beforeEach(()=>{
      cy.visit('/datasets')
      cy.findByPlaceholderText("Search by dataset name or description").type(
        "source"
      );
    })

    it('should show a bookmarked dataset', ()=>{
      assertBookmarked()
    })

    it('should NOT show a bookmarked dataset', ()=>{
      assertNotBookmarked()
    })
  })
})